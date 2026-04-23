import chess
import functools
from typing import Optional, Callable


def sum_over_squares(func: Callable) -> Callable:
    _cache = {}

    @functools.wraps(func)
    def wrapper(
        board: chess.Board, sq: Optional[chess.Square] = None, *args, **kwargs
    ) -> int:
        # Use board's transposition key + other args as a hashable cache key
        board_key = board._transposition_key()
        key = (board_key, sq, args, tuple(sorted(kwargs.items())))
        
        if key in _cache:
            return _cache[key]
            
        if sq is None:
            res = sum(func(board, s, *args, **kwargs) for s in chess.SQUARES)
        else:
            res = func(board, sq, *args, **kwargs)
        
        if len(_cache) > 10000:
            _cache.clear()
            
        _cache[key] = res
        return res

    return wrapper


def get_x(sq: chess.Square) -> int:
    return chess.square_file(sq)


def get_y(sq: chess.Square) -> int:
    return 7 - chess.square_rank(sq)


def make_sq(x: int, y: int) -> Optional[chess.Square]:
    if 0 <= x <= 7 and 0 <= y <= 7:
        return chess.square(x, 7 - y)
    return None


_get_p_cache = {}

def get_p(board: chess.Board, x: int, y: int) -> Optional[chess.Piece]:
    # Use the same transposition key strategy
    board_key = board._transposition_key()
    key = (board_key, x, y)
    
    if key in _get_p_cache:
        return _get_p_cache[key]

    if 0 <= x <= 7 and 0 <= y <= 7:
        res = board.piece_at(chess.square(x, 7 - y))
    else:
        res = None
        
    if len(_get_p_cache) > 20000:
        _get_p_cache.clear()
        
    _get_p_cache[key] = res
    return res


def is_white(p: Optional[chess.Piece], pt: Optional[chess.PieceType] = None) -> bool:
    if not p or p.color != chess.WHITE:
        return False
    return pt is None or p.piece_type == pt


def is_black(p: Optional[chess.Piece], pt: Optional[chess.PieceType] = None) -> bool:
    if not p or p.color != chess.BLACK:
        return False
    return pt is None or p.piece_type == pt


def piece_idx(p: Optional[chess.Piece]) -> int:
    if not p:
        return -1
    types = {
        chess.PAWN: 1,
        chess.KNIGHT: 2,
        chess.BISHOP: 3,
        chess.ROOK: 4,
        chess.QUEEN: 5,
    }
    idx = types.get(p.piece_type, -1)
    if idx == -1:
        return -1
    return idx if p.color == chess.WHITE else idx + 6


def main_evaluation(board: chess.Board, is_single_arg: bool = False) -> int:
    mg = middle_game_evaluation(board)
    eg = end_game_evaluation(board)
    p = phase(board)
    rule50_val = rule50(board)
    eg = int(eg * scale_factor(board, eg) / 64)
    v = int((mg * p + int(eg * (128 - p))) / 128)
    if is_single_arg:
        v = int(v / 16) * 16
    v += tempo(board)
    v = int(v * (100 - rule50_val) / 100)
    return v


@sum_over_squares
def isolated(board: chess.Board, sq: chess.Square) -> int:
    x, y = get_x(sq), get_y(sq)
    if not is_white(get_p(board, x, y), chess.PAWN):
        return 0
    for file_y in range(8):
        if is_white(get_p(board, x - 1, file_y), chess.PAWN):
            return 0
        if is_white(get_p(board, x + 1, file_y), chess.PAWN):
            return 0
    return 1


@sum_over_squares
def opposed(board: chess.Board, sq: chess.Square) -> int:
    x, y = get_x(sq), get_y(sq)
    if not is_white(get_p(board, x, y), chess.PAWN):
        return 0
    for cur_y in range(y):
        if is_black(get_p(board, x, cur_y), chess.PAWN):
            return 1
    return 0


@sum_over_squares
def rank(board: chess.Board, sq: chess.Square) -> int:
    return 8 - get_y(sq)


@sum_over_squares
def file(board: chess.Board, sq: chess.Square) -> int:
    return 1 + get_x(sq)


@sum_over_squares
def phalanx(board: chess.Board, sq: chess.Square) -> int:
    x, y = get_x(sq), get_y(sq)
    if not is_white(get_p(board, x, y), chess.PAWN):
        return 0
    if is_white(get_p(board, x - 1, y), chess.PAWN):
        return 1
    if is_white(get_p(board, x + 1, y), chess.PAWN):
        return 1
    return 0


@sum_over_squares
def supported(board: chess.Board, sq: chess.Square) -> int:
    x, y = get_x(sq), get_y(sq)
    if not is_white(get_p(board, x, y), chess.PAWN):
        return 0
    res = 1 if is_white(get_p(board, x - 1, y + 1), chess.PAWN) else 0
    res += 1 if is_white(get_p(board, x + 1, y + 1), chess.PAWN) else 0
    return res


@sum_over_squares
def backward(board: chess.Board, sq: chess.Square) -> int:
    x, y = get_x(sq), get_y(sq)
    if not is_white(get_p(board, x, y), chess.PAWN):
        return 0
    for cur_y in range(y, 8):
        if is_white(get_p(board, x - 1, cur_y), chess.PAWN) or is_white(
            get_p(board, x + 1, cur_y), chess.PAWN
        ):
            return 0
    if (
        is_black(get_p(board, x - 1, y - 2), chess.PAWN)
        or is_black(get_p(board, x + 1, y - 2), chess.PAWN)
        or is_black(get_p(board, x, y - 1), chess.PAWN)
    ):
        return 1
    return 0


@sum_over_squares
def doubled(board: chess.Board, sq: chess.Square) -> int:
    x, y = get_x(sq), get_y(sq)
    if not is_white(get_p(board, x, y), chess.PAWN):
        return 0
    if not is_white(get_p(board, x, y + 1), chess.PAWN):
        return 0
    if is_white(get_p(board, x - 1, y + 1), chess.PAWN):
        return 0
    if is_white(get_p(board, x + 1, y + 1), chess.PAWN):
        return 0
    return 1


@sum_over_squares
def connected(board: chess.Board, sq: chess.Square) -> int:
    if supported(board, sq) or phalanx(board, sq):
        return 1
    return 0


def middle_game_evaluation(board: chess.Board, nowinnable: bool = False) -> int:
    pos2 = board.mirror()
    v = 0
    v += piece_value_mg(board) - piece_value_mg(pos2)
    v += psqt_mg(board) - psqt_mg(pos2)
    v += imbalance_total(board)
    v += pawns_mg(board) - pawns_mg(pos2)
    v += pieces_mg(board) - pieces_mg(pos2)
    v += mobility_mg(board) - mobility_mg(pos2)
    v += threats_mg(board) - threats_mg(pos2)
    v += passed_mg(board) - passed_mg(pos2)
    v += space(board) - space(pos2)
    v += king_mg(board) - king_mg(pos2)
    if not nowinnable:
        v += winnable_total_mg(board, v)
    return v


def end_game_evaluation(board: chess.Board, nowinnable: bool = False) -> int:
    pos2 = board.mirror()
    v = 0
    v += piece_value_eg(board) - piece_value_eg(pos2)
    v += psqt_eg(board) - psqt_eg(pos2)
    v += imbalance_total(board)
    v += pawns_eg(board) - pawns_eg(pos2)
    v += pieces_eg(board) - pieces_eg(pos2)
    v += mobility_eg(board) - mobility_eg(pos2)
    v += threats_eg(board) - threats_eg(pos2)
    v += passed_eg(board) - passed_eg(pos2)
    v += king_eg(board) - king_eg(pos2)
    if not nowinnable:
        v += winnable_total_eg(board, v)
    return v


def scale_factor(board: chess.Board, eg: Optional[int] = None) -> int:
    if eg is None:
        eg = end_game_evaluation(board)
    pos2 = board.mirror()
    pos_w = board if eg > 0 else pos2
    pos_b = pos2 if eg > 0 else board
    sf = 64
    pc_w = pawn_count(pos_w)
    pc_b = pawn_count(pos_b)
    qc_w = queen_count(pos_w)
    qc_b = queen_count(pos_b)
    bc_w = bishop_count(pos_w)
    bc_b = bishop_count(pos_b)
    nc_w = knight_count(pos_w)
    nc_b = knight_count(pos_b)
    npm_w = non_pawn_material(pos_w)
    npm_b = non_pawn_material(pos_b)
    bishopValueMg = 825
    bishopValueEg = 915
    rookValueMg = 1276

    if pc_w == 0 and npm_w - npm_b <= bishopValueMg:
        sf = 0 if npm_w < rookValueMg else (4 if npm_b <= bishopValueMg else 14)
    if sf == 64:
        ob = opposite_bishops(board)
        if ob and npm_w == bishopValueMg and npm_b == bishopValueMg:
            sf = 22 + 4 * candidate_passed(pos_w)
        elif ob:
            sf = 22 + 3 * piece_count(pos_w)
        else:
            if npm_w == rookValueMg and npm_b == rookValueMg and pc_w - pc_b <= 1:
                pawnking_b = 0
                pcw_flank = [0, 0]
                for x in range(8):
                    for y in range(8):
                        if is_white(get_p(pos_w, x, y), chess.PAWN):
                            pcw_flank[1 if x < 4 else 0] = 1
                        if is_white(get_p(pos_b, x, y), chess.KING):
                            for ix in range(-1, 2):
                                for iy in range(-1, 2):
                                    if is_white(
                                        get_p(pos_b, x + ix, y + iy), chess.PAWN
                                    ):
                                        pawnking_b = 1
                if pcw_flank[0] != pcw_flank[1] and pawnking_b:
                    return 36
            if qc_w + qc_b == 1:
                sf = 37 + 3 * (bc_b + nc_b if qc_w == 1 else bc_w + nc_w)
            else:
                sf = min(sf, 36 + 7 * pc_w)
    return sf


def phase(board: chess.Board) -> int:
    midgameLimit = 15258
    endgameLimit = 3915
    npm = non_pawn_material(board) + non_pawn_material(board.mirror())
    npm = max(endgameLimit, min(npm, midgameLimit))
    return int(((npm - endgameLimit) * 128) / (midgameLimit - endgameLimit))


@sum_over_squares
def imbalance(board: chess.Board, sq: chess.Square) -> int:
    qo = [
        [0],
        [40, 38],
        [32, 255, -62],
        [0, 104, 4, 0],
        [-26, -2, 47, 105, -208],
        [-189, 24, 117, 133, -134, -6],
    ]
    qt = [
        [0],
        [36, 0],
        [9, 63, 0],
        [59, 65, 42, 0],
        [46, 39, 24, -24, 0],
        [97, 100, -42, 137, 268, 0],
    ]
    x, y = get_x(sq), get_y(sq)
    p = get_p(board, x, y)
    if not p:
        return 0
    j = piece_idx(p)
    if j < 0 or j > 5:
        return 0
    bishop = [0, 0]
    v = 0
    for tx in range(8):
        for ty in range(8):
            tp = get_p(board, tx, ty)
            if not tp:
                continue
            i = piece_idx(tp)
            if i == 9:
                bishop[0] += 1
            if i == 3:
                bishop[1] += 1
            if i % 6 > j:
                continue
            if i > 5:
                v += qt[j][i - 6]
            else:
                v += qo[j][i]
    if bishop[0] > 1:
        v += qt[j][0]
    if bishop[1] > 1:
        v += qo[j][0]
    return v


@sum_over_squares
def bishop_count(board: chess.Board, sq: chess.Square) -> int:
    if is_white(get_p(board, get_x(sq), get_y(sq)), chess.BISHOP):
        return 1
    return 0


def bishop_pair(board: chess.Board, sq: Optional[chess.Square] = None) -> int:
    if bishop_count(board) < 2:
        return 0
    if sq is None:
        return 1438
    if is_white(get_p(board, get_x(sq), get_y(sq)), chess.BISHOP):
        return 1
    return 0


@sum_over_squares
def pinned_direction(board: chess.Board, sq: chess.Square) -> int:
    x, y = get_x(sq), get_y(sq)
    p = get_p(board, x, y)
    if not p:
        return 0
    color = 1 if p.color == chess.WHITE else -1
    for i in range(8):
        ix = (i + (i > 3)) % 3 - 1
        iy = int((i + (i > 3)) / 3) - 1
        king = False
        for d in range(1, 8):
            nx, ny = x + d * ix, y + d * iy
            if not (0 <= nx <= 7 and 0 <= ny <= 7):
                break
            b = get_p(board, nx, ny)
            if b and b.color == chess.WHITE and b.piece_type == chess.KING:
                king = True
            if b:
                break
        if king:
            for d in range(1, 8):
                nx, ny = x - d * ix, y - d * iy
                if not (0 <= nx <= 7 and 0 <= ny <= 7):
                    break
                b = get_p(board, nx, ny)
                if b:
                    if b.color == chess.BLACK:
                        if (
                            b.piece_type == chess.QUEEN
                            or (b.piece_type == chess.BISHOP and ix * iy != 0)
                            or (b.piece_type == chess.ROOK and ix * iy == 0)
                        ):
                            return abs(ix + iy * 3) * color
                    break
    return 0


@sum_over_squares
def mobility(board: chess.Board, sq: chess.Square) -> int:
    v = 0
    x, y = get_x(sq), get_y(sq)
    p = get_p(board, x, y)
    if not is_white(p) or p.piece_type in (chess.KING, chess.PAWN):
        return 0
    for tx in range(8):
        for ty in range(8):
            s2 = make_sq(tx, ty)
            if s2 and not mobility_area(board, s2):
                continue
            target_p = get_p(board, tx, ty)
            target_is_not_q = not (
                target_p
                and target_p.color == chess.WHITE
                and target_p.piece_type == chess.QUEEN
            )
            if (
                p.piece_type == chess.KNIGHT
                and knight_attack(board, s2, sq)
                and target_is_not_q
            ):
                v += 1
            if (
                p.piece_type == chess.BISHOP
                and bishop_xray_attack(board, s2, sq)
                and target_is_not_q
            ):
                v += 1
            if p.piece_type == chess.ROOK and rook_xray_attack(board, s2, sq):
                v += 1
            if p.piece_type == chess.QUEEN and queen_attack(board, s2, sq):
                v += 1
    return v


@sum_over_squares
def mobility_area(board: chess.Board, sq: chess.Square) -> int:
    x, y = get_x(sq), get_y(sq)
    p = get_p(board, x, y)
    if is_white(p, chess.KING) or is_white(p, chess.QUEEN):
        return 0
    if is_black(get_p(board, x - 1, y - 1), chess.PAWN):
        return 0
    if is_black(get_p(board, x + 1, y - 1), chess.PAWN):
        return 0
    if is_white(p, chess.PAWN) and (
        rank(board, sq) < 4 or get_p(board, x, y - 1) is not None
    ):
        return 0
    if blockers_for_king(board.mirror(), make_sq(x, 7 - y)):
        return 0
    return 1


@sum_over_squares
def mobility_bonus(board: chess.Board, sq: chess.Square, mg: bool = True) -> int:
    bonus = (
        [
            [-62, -53, -12, -4, 3, 13, 22, 28, 33],
            [-48, -20, 16, 26, 38, 51, 55, 63, 63, 68, 81, 81, 91, 98],
            [-60, -20, 2, 3, 3, 11, 22, 31, 40, 40, 41, 48, 57, 57, 62],
            [
                -30,
                -12,
                -8,
                -9,
                20,
                23,
                23,
                35,
                38,
                53,
                64,
                65,
                65,
                66,
                67,
                67,
                72,
                72,
                77,
                79,
                93,
                108,
                108,
                108,
                110,
                114,
                114,
                116,
            ],
        ]
        if mg
        else [
            [-81, -56, -31, -16, 5, 11, 17, 20, 25],
            [-59, -23, -3, 13, 24, 42, 54, 57, 65, 73, 78, 86, 88, 97],
            [-78, -17, 23, 39, 70, 99, 103, 121, 134, 139, 158, 164, 168, 169, 172],
            [
                -48,
                -30,
                -7,
                19,
                40,
                55,
                59,
                75,
                78,
                96,
                96,
                100,
                121,
                127,
                131,
                133,
                136,
                141,
                147,
                150,
                151,
                168,
                168,
                171,
                182,
                182,
                192,
                219,
            ],
        ]
    )
    p = get_p(board, get_x(sq), get_y(sq))
    if not is_white(p):
        return 0
    mapping = {chess.KNIGHT: 0, chess.BISHOP: 1, chess.ROOK: 2, chess.QUEEN: 3}
    idx = mapping.get(p.piece_type, -1)
    if idx < 0:
        return 0
    return bonus[idx][mobility(board, sq)]


@sum_over_squares
def knight_attack(
    board: chess.Board, sq: chess.Square, s2: Optional[chess.Square] = None
) -> int:
    v = 0
    x, y = get_x(sq), get_y(sq)
    for i in range(8):
        ix = ((i > 3) + 1) * (((i % 4) > 1) * 2 - 1)
        iy = (2 - int(i > 3)) * (int(i % 2 == 0) * 2 - 1)
        nx, ny = x + ix, y + iy
        b = get_p(board, nx, ny)
        if (
            is_white(b, chess.KNIGHT)
            and (s2 is None or (get_x(s2) == nx and get_y(s2) == ny))
            and not pinned(board, make_sq(nx, ny))
        ):
            v += 1
    return v


@sum_over_squares
def bishop_xray_attack(
    board: chess.Board, sq: chess.Square, s2: Optional[chess.Square] = None
) -> int:
    v = 0
    x, y = get_x(sq), get_y(sq)
    for i in range(4):
        ix = int(i > 1) * 2 - 1
        iy = int(i % 2 == 0) * 2 - 1
        for d in range(1, 8):
            nx, ny = x + d * ix, y + d * iy
            if not (0 <= nx <= 7 and 0 <= ny <= 7):
                break
            b = get_p(board, nx, ny)
            if is_white(b, chess.BISHOP) and (
                s2 is None or (get_x(s2) == nx and get_y(s2) == ny)
            ):
                dir_val = pinned_direction(board, make_sq(nx, ny))
                if dir_val == 0 or abs(ix + iy * 3) == dir_val:
                    v += 1
            if b and not (b.piece_type == chess.QUEEN):
                break
    return v


@sum_over_squares
def rook_xray_attack(
    board: chess.Board, sq: chess.Square, s2: Optional[chess.Square] = None
) -> int:
    v = 0
    x, y = get_x(sq), get_y(sq)
    for i in range(4):
        ix = -1 if i == 0 else (1 if i == 1 else 0)
        iy = -1 if i == 2 else (1 if i == 3 else 0)
        for d in range(1, 8):
            nx, ny = x + d * ix, y + d * iy
            if not (0 <= nx <= 7 and 0 <= ny <= 7):
                break
            b = get_p(board, nx, ny)
            if is_white(b, chess.ROOK) and (
                s2 is None or (get_x(s2) == nx and get_y(s2) == ny)
            ):
                dir_val = pinned_direction(board, make_sq(nx, ny))
                if dir_val == 0 or abs(ix + iy * 3) == dir_val:
                    v += 1
            if b and not (b.piece_type in (chess.ROOK, chess.QUEEN)):
                break
    return v


@sum_over_squares
def queen_attack(
    board: chess.Board, sq: chess.Square, s2: Optional[chess.Square] = None
) -> int:
    v = 0
    x, y = get_x(sq), get_y(sq)
    for i in range(8):
        ix = (i + (i > 3)) % 3 - 1
        iy = int((i + (i > 3)) / 3) - 1
        for d in range(1, 8):
            nx, ny = x + d * ix, y + d * iy
            if not (0 <= nx <= 7 and 0 <= ny <= 7):
                break
            b = get_p(board, nx, ny)
            if is_white(b, chess.QUEEN) and (
                s2 is None or (get_x(s2) == nx and get_y(s2) == ny)
            ):
                dir_val = pinned_direction(board, make_sq(nx, ny))
                if dir_val == 0 or abs(ix + iy * 3) == dir_val:
                    v += 1
            if b:
                break
    return v


@sum_over_squares
def outpost(board: chess.Board, sq: chess.Square) -> int:
    p = get_p(board, get_x(sq), get_y(sq))
    if not is_white(p) or p.piece_type not in (chess.KNIGHT, chess.BISHOP):
        return 0
    if not outpost_square(board, sq):
        return 0
    return 1


@sum_over_squares
def outpost_square(board: chess.Board, sq: chess.Square) -> int:
    x, y = get_x(sq), get_y(sq)
    if rank(board, sq) < 4 or rank(board, sq) > 6:
        return 0
    if not is_white(get_p(board, x - 1, y + 1), chess.PAWN) and not is_white(
        get_p(board, x + 1, y + 1), chess.PAWN
    ):
        return 0
    if pawn_attacks_span(board, sq):
        return 0
    return 1


@sum_over_squares
def reachable_outpost(board: chess.Board, sq: chess.Square) -> int:
    x, y = get_x(sq), get_y(sq)
    p = get_p(board, x, y)
    if not is_white(p) or p.piece_type not in (chess.KNIGHT, chess.BISHOP):
        return 0
    v = 0
    for tx in range(8):
        for ty in range(2, 5):
            t_sq = make_sq(tx, ty)
            target = get_p(board, tx, ty)
            if (
                not is_white(target)
                and target is not None
                and target.color == chess.WHITE
            ):
                continue  # Matches "PNBRQK".indexOf() < 0
            is_empty_or_black = target is None or target.color == chess.BLACK

            if is_empty_or_black:
                cond1 = (
                    p.piece_type == chess.KNIGHT
                    and knight_attack(board, t_sq, sq)
                    and outpost_square(board, t_sq)
                )
                cond2 = (
                    p.piece_type == chess.BISHOP
                    and bishop_xray_attack(board, t_sq, sq)
                    and outpost_square(board, t_sq)
                )
                if cond1 or cond2:
                    support = (
                        2
                        if (
                            is_white(get_p(board, tx - 1, ty + 1), chess.PAWN)
                            or is_white(get_p(board, tx + 1, ty + 1), chess.PAWN)
                        )
                        else 1
                    )
                    v = max(v, support)
    return v


@sum_over_squares
def minor_behind_pawn(board: chess.Board, sq: chess.Square) -> int:
    x, y = get_x(sq), get_y(sq)
    p = get_p(board, x, y)
    if not is_white(p) or p.piece_type not in (chess.KNIGHT, chess.BISHOP):
        return 0
    front = get_p(board, x, y - 1)
    if not front or front.piece_type != chess.PAWN:
        return 0
    return 1


@sum_over_squares
def bishop_pawns(board: chess.Board, sq: chess.Square) -> int:
    x, y = get_x(sq), get_y(sq)
    if not is_white(get_p(board, x, y), chess.BISHOP):
        return 0
    c = (x + y) % 2
    v = 0
    blocked = 0
    for tx in range(8):
        for ty in range(8):
            tp = get_p(board, tx, ty)
            if is_white(tp, chess.PAWN) and c == (tx + ty) % 2:
                v += 1
            if (
                is_white(tp, chess.PAWN)
                and tx > 1
                and tx < 6
                and get_p(board, tx, ty - 1) is not None
            ):
                blocked += 1
    return v * (blocked + (0 if pawn_attack(board, sq) > 0 else 1))


@sum_over_squares
def rook_on_file(board: chess.Board, sq: chess.Square) -> int:
    x, y = get_x(sq), get_y(sq)
    if not is_white(get_p(board, x, y), chess.ROOK):
        return 0
    open_file = 1
    for ty in range(8):
        if is_white(get_p(board, x, ty), chess.PAWN):
            return 0
        if is_black(get_p(board, x, ty), chess.PAWN):
            open_file = 0
    return open_file + 1


@sum_over_squares
def trapped_rook(board: chess.Board, sq: chess.Square) -> int:
    x, y = get_x(sq), get_y(sq)
    if not is_white(get_p(board, x, y), chess.ROOK):
        return 0
    if rook_on_file(board, sq):
        return 0
    if mobility(board, sq) > 3:
        return 0
    kx = ky = 0
    for tx in range(8):
        for ty in range(8):
            if is_white(get_p(board, tx, ty), chess.KING):
                kx, ky = tx, ty
    if (kx < 4) != (x < kx):
        return 0
    return 1


@sum_over_squares
def weak_queen(board: chess.Board, sq: chess.Square) -> int:
    x, y = get_x(sq), get_y(sq)
    if not is_white(get_p(board, x, y), chess.QUEEN):
        return 0
    for i in range(8):
        ix = (i + (i > 3)) % 3 - 1
        iy = int((i + (i > 3)) / 3) - 1
        count = 0
        for d in range(1, 8):
            nx, ny = x + d * ix, y + d * iy
            if not (0 <= nx <= 7 and 0 <= ny <= 7):
                break
            b = get_p(board, nx, ny)
            if is_black(b, chess.ROOK) and (ix == 0 or iy == 0) and count == 1:
                return 1
            if is_black(b, chess.BISHOP) and (ix != 0 and iy != 0) and count == 1:
                return 1
            if b:
                count += 1
    return 0


@sum_over_squares
def space_area(board: chess.Board, sq: chess.Square) -> int:
    x, y = get_x(sq), get_y(sq)
    v = 0
    rank_val = rank(board, sq)
    file_val = file(board, sq)
    if (
        (2 <= rank_val <= 4 and 3 <= file_val <= 6)
        and not is_white(get_p(board, x, y), chess.PAWN)
        and not is_black(get_p(board, x - 1, y - 1), chess.PAWN)
        and not is_black(get_p(board, x + 1, y - 1), chess.PAWN)
    ):
        v += 1
        if (
            is_white(get_p(board, x, y - 1), chess.PAWN)
            or is_white(get_p(board, x, y - 2), chess.PAWN)
            or is_white(get_p(board, x, y - 3), chess.PAWN)
        ) and not attack(board.mirror(), make_sq(x, 7 - y)):
            v += 1
    return v


@sum_over_squares
def pawn_attack(board: chess.Board, sq: chess.Square) -> int:
    v = 0
    x, y = get_x(sq), get_y(sq)
    if is_white(get_p(board, x - 1, y + 1), chess.PAWN):
        v += 1
    if is_white(get_p(board, x + 1, y + 1), chess.PAWN):
        v += 1
    return v


@sum_over_squares
def king_attack(board: chess.Board, sq: chess.Square) -> int:
    x, y = get_x(sq), get_y(sq)
    for i in range(8):
        ix = (i + (i > 3)) % 3 - 1
        iy = int((i + (i > 3)) / 3) - 1
        if is_white(get_p(board, x + ix, y + iy), chess.KING):
            return 1
    return 0


@sum_over_squares
def attack(board: chess.Board, sq: chess.Square) -> int:
    v = 0
    v += pawn_attack(board, sq)
    v += king_attack(board, sq)
    v += knight_attack(board, sq)
    v += bishop_xray_attack(board, sq)
    v += rook_xray_attack(board, sq)
    v += queen_attack(board, sq)
    return v


@sum_over_squares
def non_pawn_material(board: chess.Board, sq: chess.Square) -> int:
    p = get_p(board, get_x(sq), get_y(sq))
    if is_white(p) and p.piece_type in (
        chess.KNIGHT,
        chess.BISHOP,
        chess.ROOK,
        chess.QUEEN,
    ):
        return piece_value_bonus(board, sq, True)
    return 0


@sum_over_squares
def safe_pawn(board: chess.Board, sq: chess.Square) -> int:
    x, y = get_x(sq), get_y(sq)
    if not is_white(get_p(board, x, y), chess.PAWN):
        return 0
    if attack(board, sq):
        return 1
    if not attack(board.mirror(), make_sq(x, 7 - y)):
        return 1
    return 0


@sum_over_squares
def threat_safe_pawn(board: chess.Board, sq: chess.Square) -> int:
    x, y = get_x(sq), get_y(sq)
    p = get_p(board, x, y)
    if not is_black(p) or p.piece_type in (chess.KING, chess.PAWN):
        return 0
    if not pawn_attack(board, sq):
        return 0
    if safe_pawn(board, make_sq(x - 1, y + 1)) or safe_pawn(
        board, make_sq(x + 1, y + 1)
    ):
        return 1
    return 0


@sum_over_squares
def weak_enemies(board: chess.Board, sq: chess.Square) -> int:
    x, y = get_x(sq), get_y(sq)
    if not is_black(get_p(board, x, y)):
        return 0
    if is_black(get_p(board, x - 1, y - 1), chess.PAWN):
        return 0
    if is_black(get_p(board, x + 1, y - 1), chess.PAWN):
        return 0
    if not attack(board, sq):
        return 0
    if attack(board, sq) <= 1 and attack(board.mirror(), make_sq(x, 7 - y)) > 1:
        return 0
    return 1


@sum_over_squares
def minor_threat(board: chess.Board, sq: chess.Square) -> int:
    x, y = get_x(sq), get_y(sq)
    p = get_p(board, x, y)
    if not is_black(p):
        return 0
    types = {
        chess.PAWN: 0,
        chess.KNIGHT: 1,
        chess.BISHOP: 2,
        chess.ROOK: 3,
        chess.QUEEN: 4,
        chess.KING: 5,
    }
    pt = types.get(p.piece_type, -1)
    if not knight_attack(board, sq) and not bishop_xray_attack(board, sq):
        return 0
    if (
        p.piece_type == chess.PAWN
        or not (
            is_black(get_p(board, x - 1, y - 1), chess.PAWN)
            or is_black(get_p(board, x + 1, y - 1), chess.PAWN)
            or (
                attack(board, sq) <= 1 and attack(board.mirror(), make_sq(x, 7 - y)) > 1
            )
        )
    ) and not weak_enemies(board, sq):
        return 0
    return pt + 1


@sum_over_squares
def rook_threat(board: chess.Board, sq: chess.Square) -> int:
    p = get_p(board, get_x(sq), get_y(sq))
    if not is_black(p):
        return 0
    types = {
        chess.PAWN: 0,
        chess.KNIGHT: 1,
        chess.BISHOP: 2,
        chess.ROOK: 3,
        chess.QUEEN: 4,
        chess.KING: 5,
    }
    pt = types.get(p.piece_type, -1)
    if not weak_enemies(board, sq):
        return 0
    if not rook_xray_attack(board, sq):
        return 0
    return pt + 1


@sum_over_squares
def hanging(board: chess.Board, sq: chess.Square) -> int:
    if not weak_enemies(board, sq):
        return 0
    x, y = get_x(sq), get_y(sq)
    if not is_black(get_p(board, x, y), chess.PAWN) and attack(board, sq) > 1:
        return 1
    if not attack(board.mirror(), make_sq(x, 7 - y)):
        return 1
    return 0


@sum_over_squares
def king_threat(board: chess.Board, sq: chess.Square) -> int:
    p = get_p(board, get_x(sq), get_y(sq))
    if not is_black(p) or p.piece_type == chess.KING:
        return 0
    if not weak_enemies(board, sq):
        return 0
    if not king_attack(board, sq):
        return 0
    return 1


@sum_over_squares
def pawn_push_threat(board: chess.Board, sq: chess.Square) -> int:
    x, y = get_x(sq), get_y(sq)
    if not is_black(get_p(board, x, y)):
        return 0
    for ix in [-1, 1]:
        if (
            is_white(get_p(board, x + ix, y + 2), chess.PAWN)
            and get_p(board, x + ix, y + 1) is None
            and not is_black(get_p(board, x + ix - 1, y), chess.PAWN)
            and not is_black(get_p(board, x + ix + 1, y), chess.PAWN)
            and (
                attack(board, make_sq(x + ix, y + 1))
                or not attack(board.mirror(), make_sq(x + ix, 6 - y))
            )
        ):
            return 1

        if (
            y == 3
            and is_white(get_p(board, x + ix, y + 3), chess.PAWN)
            and get_p(board, x + ix, y + 2) is None
            and get_p(board, x + ix, y + 1) is None
            and not is_black(get_p(board, x + ix - 1, y), chess.PAWN)
            and not is_black(get_p(board, x + ix + 1, y), chess.PAWN)
            and (
                attack(board, make_sq(x + ix, y + 1))
                or not attack(board.mirror(), make_sq(x + ix, 6 - y))
            )
        ):
            return 1
    return 0


@sum_over_squares
def candidate_passed(board: chess.Board, sq: chess.Square) -> int:
    x, y = get_x(sq), get_y(sq)
    if not is_white(get_p(board, x, y), chess.PAWN):
        return 0
    ty1 = 8
    ty2 = 8
    for cur_y in range(y - 1, -1, -1):
        if is_white(get_p(board, x, cur_y), chess.PAWN):
            return 0
        if is_black(get_p(board, x, cur_y), chess.PAWN):
            ty1 = cur_y
        if is_black(get_p(board, x - 1, cur_y), chess.PAWN) or is_black(
            get_p(board, x + 1, cur_y), chess.PAWN
        ):
            ty2 = cur_y

    if ty1 == 8 and ty2 >= y - 1:
        return 1
    if ty2 < y - 2 or ty1 < y - 1:
        return 0
    if ty2 >= y and ty1 == y - 1 and y < 4:
        if (
            is_white(get_p(board, x - 1, y + 1), chess.PAWN)
            and not is_black(get_p(board, x - 1, y), chess.PAWN)
            and not is_black(get_p(board, x - 2, y - 1), chess.PAWN)
        ):
            return 1
        if (
            is_white(get_p(board, x + 1, y + 1), chess.PAWN)
            and not is_black(get_p(board, x + 1, y), chess.PAWN)
            and not is_black(get_p(board, x + 2, y - 1), chess.PAWN)
        ):
            return 1

    if is_black(get_p(board, x, y - 1), chess.PAWN):
        return 0
    lever = int(is_black(get_p(board, x - 1, y - 1), chess.PAWN)) + int(
        is_black(get_p(board, x + 1, y - 1), chess.PAWN)
    )
    leverpush = int(is_black(get_p(board, x - 1, y - 2), chess.PAWN)) + int(
        is_black(get_p(board, x + 1, y - 2), chess.PAWN)
    )
    phalanx_val = int(is_white(get_p(board, x - 1, y), chess.PAWN)) + int(
        is_white(get_p(board, x + 1, y), chess.PAWN)
    )

    if lever - supported(board, sq) > 1:
        return 0
    if leverpush - phalanx_val > 0:
        return 0
    if lever > 0 and leverpush > 0:
        return 0
    return 1


@sum_over_squares
def king_proximity(board: chess.Board, sq: chess.Square) -> int:
    if not passed_leverable(board, sq):
        return 0
    r = rank(board, sq) - 1
    w = 5 * r - 13 if r > 2 else 0
    v = 0
    if w <= 0:
        return 0
    x, y = get_x(sq), get_y(sq)
    for tx in range(8):
        for ty in range(8):
            if is_black(get_p(board, tx, ty), chess.KING):
                v += int(min(max(abs(ty - y + 1), abs(tx - x)), 5) * 19 / 4) * w
            if is_white(get_p(board, tx, ty), chess.KING):
                v -= min(max(abs(ty - y + 1), abs(tx - x)), 5) * 2 * w
                if y > 1:
                    v -= min(max(abs(ty - y + 2), abs(tx - x)), 5) * w
    return v


@sum_over_squares
def passed_block(board: chess.Board, sq: chess.Square) -> int:
    if not passed_leverable(board, sq):
        return 0
    if rank(board, sq) < 4:
        return 0
    x, y = get_x(sq), get_y(sq)
    if get_p(board, x, y - 1) is not None:
        return 0
    r = rank(board, sq) - 1
    w = 5 * r - 13 if r > 2 else 0
    pos2 = board.mirror()
    defended = unsafe = wunsafe = defended1 = unsafe1 = 0

    for cur_y in range(y - 1, -1, -1):
        if attack(board, make_sq(x, cur_y)):
            defended += 1
        if attack(pos2, make_sq(x, 7 - cur_y)):
            unsafe += 1
        if attack(pos2, make_sq(x - 1, 7 - cur_y)):
            wunsafe += 1
        if attack(pos2, make_sq(x + 1, 7 - cur_y)):
            wunsafe += 1
        if cur_y == y - 1:
            defended1, unsafe1 = defended, unsafe

    for cur_y in range(y + 1, 8):
        p_w = get_p(board, x, cur_y)
        if is_white(p_w) and p_w.piece_type in (chess.ROOK, chess.QUEEN):
            defended1 = defended = y
        p_b = get_p(board, x, cur_y)
        if is_black(p_b) and p_b.piece_type in (chess.ROOK, chess.QUEEN):
            unsafe1 = unsafe = y

    k = (
        35
        if unsafe == 0 and wunsafe == 0
        else (20 if unsafe == 0 else (9 if unsafe1 == 0 else 0))
    ) + (5 if defended1 != 0 else 0)
    return k * w


@sum_over_squares
def passed_file(board: chess.Board, sq: chess.Square) -> int:
    if not passed_leverable(board, sq):
        return 0
    f = file(board, sq)
    return min(f - 1, 8 - f)


@sum_over_squares
def passed_rank(board: chess.Board, sq: chess.Square) -> int:
    if not passed_leverable(board, sq):
        return 0
    return rank(board, sq) - 1


def pawnless_flank(board: chess.Board) -> int:
    pawns = [0] * 8
    kx = 0
    for x in range(8):
        for y in range(8):
            if get_p(board, x, y) and get_p(board, x, y).piece_type == chess.PAWN:
                pawns[x] += 1
            if is_black(get_p(board, x, y), chess.KING):
                kx = x
    if kx == 0:
        s = sum(pawns[0:3])
    elif kx < 3:
        s = sum(pawns[0:4])
    elif kx < 5:
        s = sum(pawns[2:6])
    elif kx < 7:
        s = sum(pawns[4:8])
    else:
        s = sum(pawns[5:8])
    return 1 if s == 0 else 0


@sum_over_squares
def strength_square(board: chess.Board, sq: chess.Square) -> int:
    v = 5
    x, y = get_x(sq), get_y(sq)
    kx = min(6, max(1, x))
    weakness = [
        [-6, 81, 93, 58, 39, 18, 25],
        [-43, 61, 35, -49, -29, -11, -63],
        [-10, 75, 23, -2, 32, 3, -45],
        [-39, -13, -29, -52, -48, -67, -166],
    ]
    for tx in range(kx - 1, kx + 2):
        us = 0
        for ty in range(7, y - 1, -1):
            if (
                is_black(get_p(board, tx, ty), chess.PAWN)
                and not is_white(get_p(board, tx - 1, ty + 1), chess.PAWN)
                and not is_white(get_p(board, tx + 1, ty + 1), chess.PAWN)
            ):
                us = ty
        f = min(tx, 7 - tx)
        if us < len(weakness[f]):
            v += weakness[f][us]
    return v


@sum_over_squares
def storm_square(board: chess.Board, sq: chess.Square, eg: bool = False) -> int:
    v = 0
    ev = 5
    x, y = get_x(sq), get_y(sq)
    kx = min(6, max(1, x))
    unblockedstorm = [
        [85, -289, -166, 97, 50, 45, 50],
        [46, -25, 122, 45, 37, -10, 20],
        [-6, 51, 168, 34, -2, -22, -14],
        [-15, -11, 101, 4, 11, -15, -29],
    ]
    blockedstorm = [[0, 0, 76, -10, -7, -4, -1], [0, 0, 78, 15, 10, 6, 2]]
    for tx in range(kx - 1, kx + 2):
        us, them = 0, 0
        for ty in range(7, y - 1, -1):
            if (
                is_black(get_p(board, tx, ty), chess.PAWN)
                and not is_white(get_p(board, tx - 1, ty + 1), chess.PAWN)
                and not is_white(get_p(board, tx + 1, ty + 1), chess.PAWN)
            ):
                us = ty
            if is_white(get_p(board, tx, ty), chess.PAWN):
                them = ty
        f = min(tx, 7 - tx)
        if us > 0 and them == us + 1:
            v += blockedstorm[0][them]
            ev += blockedstorm[1][them]
        else:
            v += unblockedstorm[f][them]
    return ev if eg else v


def shelter_strength(board: chess.Board, sq: Optional[chess.Square] = None) -> int:
    w = 0
    s = 1024
    tx = None
    for x in range(8):
        for y in range(8):
            p = get_p(board, x, y)
            if (
                is_black(p, chess.KING)
                or (
                    board.has_kingside_castling_rights(chess.BLACK)
                    and x == 6
                    and y == 0
                )
                or (
                    board.has_queenside_castling_rights(chess.BLACK)
                    and x == 2
                    and y == 0
                )
            ):
                w1 = strength_square(board, make_sq(x, y))
                s1 = storm_square(board, make_sq(x, y))
                if s1 - w1 < s - w:
                    w, s, tx = w1, s1, max(1, min(6, x))
    if sq is None:
        return w
    sq_x, sq_y = get_x(sq), get_y(sq)
    if (
        tx is not None
        and is_black(get_p(board, sq_x, sq_y), chess.PAWN)
        and tx - 1 <= sq_x <= tx + 1
    ):
        for cur_y in range(sq_y - 1, -1, -1):
            if is_black(get_p(board, sq_x, cur_y), chess.PAWN):
                return 0
        return 1
    return 0


def shelter_storm(board: chess.Board, sq: Optional[chess.Square] = None) -> int:
    w = 0
    s = 1024
    tx = None
    for x in range(8):
        for y in range(8):
            p = get_p(board, x, y)
            if (
                is_black(p, chess.KING)
                or (
                    board.has_kingside_castling_rights(chess.BLACK)
                    and x == 6
                    and y == 0
                )
                or (
                    board.has_queenside_castling_rights(chess.BLACK)
                    and x == 2
                    and y == 0
                )
            ):
                w1 = strength_square(board, make_sq(x, y))
                s1 = storm_square(board, make_sq(x, y))
                if s1 - w1 < s - w:
                    w, s, tx = w1, s1, max(1, min(6, x))
    if sq is None:
        return s
    sq_x, sq_y = get_x(sq), get_y(sq)
    p_sq = get_p(board, sq_x, sq_y)
    if (
        tx is not None
        and p_sq
        and p_sq.piece_type == chess.PAWN
        and tx - 1 <= sq_x <= tx + 1
    ):
        for cur_y in range(sq_y - 1, -1, -1):
            target = get_p(board, sq_x, cur_y)
            if (
                target
                and target.piece_type == p_sq.piece_type
                and target.color == p_sq.color
            ):
                return 0
        return 1
    return 0


def king_pawn_distance(board: chess.Board, sq: Optional[chess.Square] = None) -> int:
    v = 6
    kx = ky = px = py = 0
    for x in range(8):
        for y in range(8):
            if is_white(get_p(board, x, y), chess.KING):
                kx, ky = x, y
    for x in range(8):
        for y in range(8):
            dist = max(abs(x - kx), abs(y - ky))
            if is_white(get_p(board, x, y), chess.PAWN) and dist < v:
                px, py, v = x, y, dist
    if sq is None or (get_x(sq) == px and get_y(sq) == py):
        return v
    return 0


@sum_over_squares
def check_attack(
    board: chess.Board, sq: chess.Square, type_: Optional[int] = None
) -> int:
    if (rook_xray_attack(board, sq) and (type_ is None or type_ in (2, 4))) or (
        queen_attack(board, sq) and (type_ is None or type_ == 3)
    ):
        for i in range(4):
            ix = -1 if i == 0 else (1 if i == 1 else 0)
            iy = -1 if i == 2 else (1 if i == 3 else 0)
            for d in range(1, 8):
                nx, ny = get_x(sq) + d * ix, get_y(sq) + d * iy
                if not (0 <= nx <= 7 and 0 <= ny <= 7):
                    break
                b = get_p(board, nx, ny)
                if is_black(b, chess.KING):
                    return 1
                if b and not is_black(b, chess.QUEEN):
                    break

    if (bishop_xray_attack(board, sq) and (type_ is None or type_ in (1, 4))) or (
        queen_attack(board, sq) and (type_ is None or type_ == 3)
    ):
        for i in range(4):
            ix = int(i > 1) * 2 - 1
            iy = int(i % 2 == 0) * 2 - 1
            for d in range(1, 8):
                nx, ny = get_x(sq) + d * ix, get_y(sq) + d * iy
                if not (0 <= nx <= 7 and 0 <= ny <= 7):
                    break
                b = get_p(board, nx, ny)
                if is_black(b, chess.KING):
                    return 1
                if b and not is_black(b, chess.QUEEN):
                    break

    if knight_attack(board, sq) and (type_ is None or type_ in (0, 4)):
        x, y = get_x(sq), get_y(sq)
        for dx, dy in [
            (2, 1),
            (2, -1),
            (1, 2),
            (1, -2),
            (-2, 1),
            (-2, -1),
            (-1, 2),
            (-1, -2),
        ]:
            if is_black(get_p(board, x + dx, y + dy), chess.KING):
                return 1
    return 0


@sum_over_squares
def safe_check(
    board: chess.Board, sq: chess.Square, type_: Optional[int] = None
) -> int:
    x, y = get_x(sq), get_y(sq)
    if is_white(get_p(board, x, y)):
        return 0
    if not check_attack(board, sq, type_):
        return 0
    pos2 = board.mirror()
    if type_ == 3 and safe_check(board, sq, 2):
        return 0
    if type_ == 1 and safe_check(board, sq, 3):
        return 0

    sq2 = make_sq(x, 7 - y)
    if not attack(pos2, sq2) or (weak_squares(board, sq) and attack(board, sq) > 1):
        if type_ != 3 or not queen_attack(pos2, sq2):
            return 1
    return 0


@sum_over_squares
def queen_count(board: chess.Board, sq: chess.Square) -> int:
    if is_white(get_p(board, get_x(sq), get_y(sq)), chess.QUEEN):
        return 1
    return 0


@sum_over_squares
def king_attackers_count(board: chess.Board, sq: chess.Square) -> int:
    x, y = get_x(sq), get_y(sq)
    p = get_p(board, x, y)
    if not is_white(p) or p.piece_type == chess.KING:
        return 0
    if p.piece_type == chess.PAWN:
        v = 0
        for dir_val in [-1, 1]:
            fr = is_white(get_p(board, x + dir_val * 2, y), chess.PAWN)
            if 0 <= x + dir_val <= 7 and king_ring(
                board, make_sq(x + dir_val, y - 1), True
            ):
                v += 0.5 if fr else 1
        return v
    for tx in range(8):
        for ty in range(8):
            s2 = make_sq(tx, ty)
            if king_ring(board, s2):
                if (
                    knight_attack(board, s2, sq)
                    or bishop_xray_attack(board, s2, sq)
                    or rook_xray_attack(board, s2, sq)
                    or queen_attack(board, s2, sq)
                ):
                    return 1
    return 0


@sum_over_squares
def king_attackers_weight(board: chess.Board, sq: chess.Square) -> int:
    if king_attackers_count(board, sq):
        p = get_p(board, get_x(sq), get_y(sq))
        if not p or p.color != chess.WHITE:
            return 0
        mapping = {
            chess.PAWN: 0,
            chess.KNIGHT: 81,
            chess.BISHOP: 52,
            chess.ROOK: 44,
            chess.QUEEN: 10,
        }
        return mapping.get(p.piece_type, 0)
    return 0


@sum_over_squares
def king_attacks(board: chess.Board, sq: chess.Square) -> int:
    p = get_p(board, get_x(sq), get_y(sq))
    if not is_white(p) or p.piece_type in (chess.KING, chess.PAWN):
        return 0
    if king_attackers_count(board, sq) == 0:
        return 0
    kx = ky = v = 0
    for x in range(8):
        for y in range(8):
            if is_black(get_p(board, x, y), chess.KING):
                kx, ky = x, y
    for x in range(kx - 1, kx + 2):
        for y in range(ky - 1, ky + 2):
            if 0 <= x <= 7 and 0 <= y <= 7 and (x != kx or y != ky):
                s2 = make_sq(x, y)
                v += knight_attack(board, s2, sq)
                v += bishop_xray_attack(board, s2, sq)
                v += rook_xray_attack(board, s2, sq)
                v += queen_attack(board, s2, sq)
    return v


@sum_over_squares
def weak_bonus(board: chess.Board, sq: chess.Square) -> int:
    if not weak_squares(board, sq):
        return 0
    if not king_ring(board, sq):
        return 0
    return 1


@sum_over_squares
def weak_squares(board: chess.Board, sq: chess.Square) -> int:
    if attack(board, sq):
        pos2 = board.mirror()
        x, y = get_x(sq), get_y(sq)
        sq2 = make_sq(x, 7 - y)
        att = attack(pos2, sq2)
        if att >= 2:
            return 0
        if att == 0:
            return 1
        if king_attack(pos2, sq2) or queen_attack(pos2, sq2):
            return 1
    return 0


def winnable(board: chess.Board, sq: Optional[chess.Square] = None) -> int:
    if sq is not None:
        return 0
    pawns = 0
    kx = [0, 0]
    ky = [0, 0]
    flanks = [0, 0]
    for x in range(8):
        open_f = [0, 0]
        for y in range(8):
            p = get_p(board, x, y)
            if p and p.piece_type == chess.PAWN:
                open_f[0 if p.color == chess.WHITE else 1] = 1
                pawns += 1
            if p and p.piece_type == chess.KING:
                kx[0 if p.color == chess.WHITE else 1] = x
                ky[0 if p.color == chess.WHITE else 1] = y
        if sum(open_f) > 0:
            flanks[0 if x < 4 else 1] = 1

    pos2 = board.mirror()
    passedCount = candidate_passed(board) + candidate_passed(pos2)
    bothFlanks = 1 if (flanks[0] and flanks[1]) else 0
    outflanking = abs(kx[0] - kx[1]) - abs(ky[0] - ky[1])
    purePawn = 1 if (non_pawn_material(board) + non_pawn_material(pos2) == 0) else 0
    almostUnwinnable = 1 if (outflanking < 0 and bothFlanks == 0) else 0
    infiltration = 1 if (ky[0] < 4 or ky[1] > 3) else 0

    return (
        9 * passedCount
        + 12 * pawns
        + 9 * outflanking
        + 21 * bothFlanks
        + 24 * infiltration
        + 51 * purePawn
        - 43 * almostUnwinnable
        - 110
    )


@sum_over_squares
def unsafe_checks(board: chess.Board, sq: chess.Square) -> int:
    if check_attack(board, sq, 0) and safe_check(board, None, 0) == 0:
        return 1
    if check_attack(board, sq, 1) and safe_check(board, None, 1) == 0:
        return 1
    if check_attack(board, sq, 2) and safe_check(board, None, 2) == 0:
        return 1
    return 0


def tempo(board: chess.Board, sq: Optional[chess.Square] = None) -> int:
    if sq is not None:
        return 0
    return 28 if board.turn == chess.WHITE else -28


@sum_over_squares
def pawn_count(board: chess.Board, sq: chess.Square) -> int:
    if is_white(get_p(board, get_x(sq), get_y(sq)), chess.PAWN):
        return 1
    return 0


@sum_over_squares
def connected_bonus(board: chess.Board, sq: chess.Square) -> int:
    if not connected(board, sq):
        return 0
    seed = [0, 7, 8, 12, 29, 48, 86]
    op = opposed(board, sq)
    ph = phalanx(board, sq)
    su = supported(board, sq)
    bl = 1 if is_black(get_p(board, get_x(sq), get_y(sq) - 1), chess.PAWN) else 0
    r = rank(board, sq)
    if r < 2 or r > 7:
        return 0
    return seed[r - 1] * (2 + ph - op) + 21 * su


@sum_over_squares
def mobility_mg(board: chess.Board, sq: chess.Square) -> int:
    return mobility_bonus(board, sq, True)


@sum_over_squares
def mobility_eg(board: chess.Board, sq: chess.Square) -> int:
    return mobility_bonus(board, sq, False)


@sum_over_squares
def piece_value_bonus(board: chess.Board, sq: chess.Square, mg: bool = True) -> int:
    a = [124, 781, 825, 1276, 2538] if mg else [206, 854, 915, 1380, 2682]
    p = get_p(board, get_x(sq), get_y(sq))
    if is_white(p) and p.piece_type != chess.KING:
        mapping = {
            chess.PAWN: 0,
            chess.KNIGHT: 1,
            chess.BISHOP: 2,
            chess.ROOK: 3,
            chess.QUEEN: 4,
        }
        idx = mapping.get(p.piece_type, -1)
        if idx >= 0:
            return a[idx]
    return 0


@sum_over_squares
def psqt_bonus(board: chess.Board, sq: chess.Square, mg: bool = True) -> int:
    bonus = (
        [
            [
                [-175, -92, -74, -73],
                [-77, -41, -27, -15],
                [-61, -17, 6, 12],
                [-35, 8, 40, 49],
                [-34, 13, 44, 51],
                [-9, 22, 58, 53],
                [-67, -27, 4, 37],
                [-201, -83, -56, -26],
            ],
            [
                [-53, -5, -8, -23],
                [-15, 8, 19, 4],
                [-7, 21, -5, 17],
                [-5, 11, 25, 39],
                [-12, 29, 22, 31],
                [-16, 6, 1, 11],
                [-17, -14, 5, 0],
                [-48, 1, -14, -23],
            ],
            [
                [-31, -20, -14, -5],
                [-21, -13, -8, 6],
                [-25, -11, -1, 3],
                [-13, -5, -4, -6],
                [-27, -15, -4, 3],
                [-22, -2, 6, 12],
                [-2, 12, 16, 18],
                [-17, -19, -1, 9],
            ],
            [
                [3, -5, -5, 4],
                [-3, 5, 8, 12],
                [-3, 6, 13, 7],
                [4, 5, 9, 8],
                [0, 14, 12, 5],
                [-4, 10, 6, 8],
                [-5, 6, 10, 8],
                [-2, -2, 1, -2],
            ],
            [
                [271, 327, 271, 198],
                [278, 303, 234, 179],
                [195, 258, 169, 120],
                [164, 190, 138, 98],
                [154, 179, 105, 70],
                [123, 145, 81, 31],
                [88, 120, 65, 33],
                [59, 89, 45, -1],
            ],
        ]
        if mg
        else [
            [
                [-96, -65, -49, -21],
                [-67, -54, -18, 8],
                [-40, -27, -8, 29],
                [-35, -2, 13, 28],
                [-45, -16, 9, 39],
                [-51, -44, -16, 17],
                [-69, -50, -51, 12],
                [-100, -88, -56, -17],
            ],
            [
                [-57, -30, -37, -12],
                [-37, -13, -17, 1],
                [-16, -1, -2, 10],
                [-20, -6, 0, 17],
                [-17, -1, -14, 15],
                [-30, 6, 4, 6],
                [-31, -20, -1, 1],
                [-46, -42, -37, -24],
            ],
            [
                [-9, -13, -10, -9],
                [-12, -9, -1, -2],
                [6, -8, -2, -6],
                [-6, 1, -9, 7],
                [-5, 8, 7, -6],
                [6, 1, -7, 10],
                [4, 5, 20, -5],
                [18, 0, 19, 13],
            ],
            [
                [-69, -57, -47, -26],
                [-55, -31, -22, -4],
                [-39, -18, -9, 3],
                [-23, -3, 13, 24],
                [-29, -6, 9, 21],
                [-38, -18, -12, 1],
                [-50, -27, -24, -8],
                [-75, -52, -43, -36],
            ],
            [
                [1, 45, 85, 76],
                [53, 100, 133, 135],
                [88, 130, 169, 175],
                [103, 156, 172, 172],
                [96, 166, 199, 199],
                [92, 172, 184, 191],
                [47, 121, 116, 131],
                [11, 59, 73, 78],
            ],
        ]
    )
    pbonus = (
        [
            [0, 0, 0, 0, 0, 0, 0, 0],
            [3, 3, 10, 19, 16, 19, 7, -5],
            [-9, -15, 11, 15, 32, 22, 5, -22],
            [-4, -23, 6, 20, 40, 17, 4, -8],
            [13, 0, -13, 1, 11, -2, -13, 5],
            [5, -12, -7, 22, -8, -5, -15, -8],
            [-7, 7, -3, -13, 5, -16, 10, -8],
            [0, 0, 0, 0, 0, 0, 0, 0],
        ]
        if mg
        else [
            [0, 0, 0, 0, 0, 0, 0, 0],
            [-10, -6, 10, 0, 14, 7, -5, -19],
            [-10, -10, -10, 4, 4, 3, -6, -4],
            [6, -2, -8, -4, -13, -12, -10, -9],
            [10, 5, 4, -5, -5, -5, 14, 9],
            [28, 20, 21, 28, 30, 7, 6, 13],
            [0, -11, 12, 21, 25, 19, 4, 7],
            [0, 0, 0, 0, 0, 0, 0, 0],
        ]
    )
    x, y = get_x(sq), get_y(sq)
    p = get_p(board, x, y)
    if not is_white(p):
        return 0
    mapping = {
        chess.PAWN: 0,
        chess.KNIGHT: 1,
        chess.BISHOP: 2,
        chess.ROOK: 3,
        chess.QUEEN: 4,
        chess.KING: 5,
    }
    i = mapping.get(p.piece_type, -1)
    if i < 0:
        return 0
    if i == 0:
        return pbonus[7 - y][x]
    return bonus[i - 1][7 - y][min(x, 7 - x)]


@sum_over_squares
def piece_value_mg(board: chess.Board, sq: chess.Square) -> int:
    return piece_value_bonus(board, sq, True)


@sum_over_squares
def piece_value_eg(board: chess.Board, sq: chess.Square) -> int:
    return piece_value_bonus(board, sq, False)


@sum_over_squares
def psqt_mg(board: chess.Board, sq: chess.Square) -> int:
    return psqt_bonus(board, sq, True)


@sum_over_squares
def psqt_eg(board: chess.Board, sq: chess.Square) -> int:
    return psqt_bonus(board, sq, False)


@sum_over_squares
def king_protector(board: chess.Board, sq: chess.Square) -> int:
    p = get_p(board, get_x(sq), get_y(sq))
    if not is_white(p) or p.piece_type not in (chess.KNIGHT, chess.BISHOP):
        return 0
    return king_distance(board, sq)


@sum_over_squares
def knight_count(board: chess.Board, sq: chess.Square) -> int:
    if is_white(get_p(board, get_x(sq), get_y(sq)), chess.KNIGHT):
        return 1
    return 0


def imbalance_total(board: chess.Board) -> int:
    pos2 = board.mirror()
    v = imbalance(board) - imbalance(pos2)
    v += bishop_pair(board) - bishop_pair(pos2)
    return int(v / 16)


@sum_over_squares
def weak_unopposed_pawn(board: chess.Board, sq: chess.Square) -> int:
    if opposed(board, sq):
        return 0
    v = 0
    if isolated(board, sq):
        v += 1
    elif backward(board, sq):
        v += 1
    return v


@sum_over_squares
def rook_count(board: chess.Board, sq: chess.Square) -> int:
    if is_white(get_p(board, get_x(sq), get_y(sq)), chess.ROOK):
        return 1
    return 0


def opposite_bishops(board: chess.Board) -> int:
    if bishop_count(board) != 1 or bishop_count(board.mirror()) != 1:
        return 0
    color = [0, 0]
    for x in range(8):
        for y in range(8):
            p = get_p(board, x, y)
            if is_white(p, chess.BISHOP):
                color[0] = (x + y) % 2
            if is_black(p, chess.BISHOP):
                color[1] = (x + y) % 2
    return 0 if color[0] == color[1] else 1


@sum_over_squares
def king_distance(board: chess.Board, sq: chess.Square) -> int:
    for x in range(8):
        for y in range(8):
            if is_white(get_p(board, x, y), chess.KING):
                return max(abs(x - get_x(sq)), abs(y - get_y(sq)))
    return 0


@sum_over_squares
def long_diagonal_bishop(board: chess.Board, sq: chess.Square) -> int:
    x, y = get_x(sq), get_y(sq)
    if not is_white(get_p(board, x, y), chess.BISHOP):
        return 0
    if x - y != 0 and x - (7 - y) != 0:
        return 0
    x1, y1 = x, y
    if min(x1, 7 - x1) > 2:
        return 0
    for i in range(min(x1, 7 - x1), 4):
        if is_black(get_p(board, x1, y1), chess.PAWN) or is_white(
            get_p(board, x1, y1), chess.PAWN
        ):
            return 0
        x1 = x1 + 1 if x1 < 4 else x1 - 1
        y1 = y1 + 1 if y1 < 4 else y1 - 1
    return 1


@sum_over_squares
def queen_attack_diagonal(
    board: chess.Board, sq: chess.Square, s2: Optional[chess.Square] = None
) -> int:
    v = 0
    x, y = get_x(sq), get_y(sq)
    for i in range(8):
        ix = (i + (i > 3)) % 3 - 1
        iy = int((i + (i > 3)) / 3) - 1
        if ix == 0 or iy == 0:
            continue
        for d in range(1, 8):
            nx, ny = x + d * ix, y + d * iy
            if not (0 <= nx <= 7 and 0 <= ny <= 7):
                break
            b = get_p(board, nx, ny)
            if is_white(b, chess.QUEEN) and (
                s2 is None or (get_x(s2) == nx and get_y(s2) == ny)
            ):
                dir_val = pinned_direction(board, make_sq(nx, ny))
                if dir_val == 0 or abs(ix + iy * 3) == dir_val:
                    v += 1
            if b:
                break
    return v


@sum_over_squares
def pinned(board: chess.Board, sq: chess.Square) -> int:
    if not is_white(get_p(board, get_x(sq), get_y(sq))):
        return 0
    return 1 if pinned_direction(board, sq) > 0 else 0


@sum_over_squares
def king_ring(board: chess.Board, sq: chess.Square, full: bool = False) -> int:
    x, y = get_x(sq), get_y(sq)
    if (
        not full
        and is_black(get_p(board, x + 1, y - 1), chess.PAWN)
        and is_black(get_p(board, x - 1, y - 1), chess.PAWN)
    ):
        return 0
    for ix in range(-2, 3):
        for iy in range(-2, 3):
            if (
                is_black(get_p(board, x + ix, y + iy), chess.KING)
                and (-1 <= ix <= 1 or x + ix == 0 or x + ix == 7)
                and (-1 <= iy <= 1 or y + iy == 0 or y + iy == 7)
            ):
                return 1
    return 0


@sum_over_squares
def slider_on_queen(board: chess.Board, sq: chess.Square) -> int:
    pos2 = board.mirror()
    if queen_count(pos2) != 1:
        return 0
    x, y = get_x(sq), get_y(sq)
    if is_white(get_p(board, x, y), chess.PAWN):
        return 0
    if is_black(get_p(board, x - 1, y - 1), chess.PAWN) or is_black(
        get_p(board, x + 1, y - 1), chess.PAWN
    ):
        return 0
    if attack(board, sq) <= 1:
        return 0
    if not mobility_area(board, sq):
        return 0
    diagonal = queen_attack_diagonal(pos2, make_sq(x, 7 - y))
    v = 2 if queen_count(board) == 0 else 1
    if diagonal and bishop_xray_attack(board, sq):
        return v
    if (
        not diagonal
        and rook_xray_attack(board, sq)
        and queen_attack(pos2, make_sq(x, 7 - y))
    ):
        return v
    return 0


@sum_over_squares
def knight_on_queen(board: chess.Board, sq: chess.Square) -> int:
    pos2 = board.mirror()
    qx = qy = -1
    for tx in range(8):
        for ty in range(8):
            if is_black(get_p(board, tx, ty), chess.QUEEN):
                if qx >= 0 or qy >= 0:
                    return 0
                qx, qy = tx, ty
    if queen_count(pos2) != 1:
        return 0
    x, y = get_x(sq), get_y(sq)
    if is_white(get_p(board, x, y), chess.PAWN):
        return 0
    if is_black(get_p(board, x - 1, y - 1), chess.PAWN) or is_black(
        get_p(board, x + 1, y - 1), chess.PAWN
    ):
        return 0
    if attack(board, sq) <= 1 and attack(pos2, make_sq(x, 7 - y)) > 1:
        return 0
    if not mobility_area(board, sq):
        return 0
    if not knight_attack(board, sq):
        return 0
    v = 2 if queen_count(board) == 0 else 1
    if abs(qx - x) == 2 and abs(qy - y) == 1:
        return v
    if abs(qx - x) == 1 and abs(qy - y) == 2:
        return v
    return 0


@sum_over_squares
def outpost_total(board: chess.Board, sq: chess.Square) -> int:
    x, y = get_x(sq), get_y(sq)
    p = get_p(board, x, y)
    if not is_white(p) or p.piece_type not in (chess.KNIGHT, chess.BISHOP):
        return 0
    knight = p.piece_type == chess.KNIGHT
    if not outpost(board, sq):
        if not knight:
            return 0
        return 1 if reachable_outpost(board, sq) else 0
    if knight and (x < 2 or x > 5):
        ea = cnt = 0
        for tx in range(8):
            for ty in range(8):
                if (
                    (
                        abs(x - tx) == 2
                        and abs(y - ty) == 1
                        or abs(x - tx) == 1
                        and abs(y - ty) == 2
                    )
                    and is_black(get_p(board, tx, ty))
                    and get_p(board, tx, ty).piece_type != chess.PAWN
                ):
                    ea = 1
                if (
                    (tx < 4 and x < 4 or tx >= 4 and x >= 4)
                    and is_black(get_p(board, tx, ty))
                    and get_p(board, tx, ty).piece_type != chess.PAWN
                ):
                    cnt += 1
        if not ea and cnt <= 1:
            return 2
    return 4 if knight else 3


@sum_over_squares
def restricted(board: chess.Board, sq: chess.Square) -> int:
    if attack(board, sq) == 0:
        return 0
    pos2 = board.mirror()
    sq2 = make_sq(get_x(sq), 7 - get_y(sq))
    if not attack(pos2, sq2):
        return 0
    if pawn_attack(pos2, sq2) > 0:
        return 0
    if attack(pos2, sq2) > 1 and attack(board, sq) == 1:
        return 0
    return 1


@sum_over_squares
def knight_defender(board: chess.Board, sq: chess.Square) -> int:
    if knight_attack(board, sq) and king_attack(board, sq):
        return 1
    return 0


def endgame_shelter(board: chess.Board, sq: Optional[chess.Square] = None) -> int:
    w = 0
    s = 1024
    e = 0
    for x in range(8):
        for y in range(8):
            p = get_p(board, x, y)
            if (
                is_black(p, chess.KING)
                or (
                    board.has_kingside_castling_rights(chess.BLACK)
                    and x == 6
                    and y == 0
                )
                or (
                    board.has_queenside_castling_rights(chess.BLACK)
                    and x == 2
                    and y == 0
                )
            ):
                w1 = strength_square(board, make_sq(x, y))
                s1 = storm_square(board, make_sq(x, y))
                e1 = storm_square(board, make_sq(x, y), True)
                if s1 - w1 < s - w:
                    w, s, e = w1, s1, e1
    if sq is None:
        return e
    return 0


def space(board: chess.Board, sq: Optional[chess.Square] = None) -> int:
    if non_pawn_material(board) + non_pawn_material(board.mirror()) < 12222:
        return 0
    pieceCount = blockedCount = 0
    for x in range(8):
        for y in range(8):
            if is_white(get_p(board, x, y)):
                pieceCount += 1
            if is_white(get_p(board, x, y), chess.PAWN) and (
                is_black(get_p(board, x, y - 1), chess.PAWN)
                or (
                    is_black(get_p(board, x - 1, y - 2), chess.PAWN)
                    and is_black(get_p(board, x + 1, y - 2), chess.PAWN)
                )
            ):
                blockedCount += 1
            if is_black(get_p(board, x, y), chess.PAWN) and (
                is_white(get_p(board, x, y + 1), chess.PAWN)
                or (
                    is_white(get_p(board, x - 1, y + 2), chess.PAWN)
                    and is_white(get_p(board, x + 1, y + 2), chess.PAWN)
                )
            ):
                blockedCount += 1
    weight = pieceCount - 3 + min(blockedCount, 9)
    return int(space_area(board, sq) * weight * weight / 16)


@sum_over_squares
def weak_lever(board: chess.Board, sq: chess.Square) -> int:
    x, y = get_x(sq), get_y(sq)
    if not is_white(get_p(board, x, y), chess.PAWN):
        return 0
    if not is_black(get_p(board, x - 1, y - 1), chess.PAWN):
        return 0
    if not is_black(get_p(board, x + 1, y - 1), chess.PAWN):
        return 0
    if is_white(get_p(board, x - 1, y + 1), chess.PAWN):
        return 0
    if is_white(get_p(board, x + 1, y + 1), chess.PAWN):
        return 0
    return 1


@sum_over_squares
def blockers_for_king(board: chess.Board, sq: chess.Square) -> int:
    if pinned_direction(board.mirror(), make_sq(get_x(sq), 7 - get_y(sq))):
        return 1
    return 0


@sum_over_squares
def rook_on_queen_file(board: chess.Board, sq: chess.Square) -> int:
    x, y = get_x(sq), get_y(sq)
    if not is_white(get_p(board, x, y), chess.ROOK):
        return 0
    for cur_y in range(8):
        p = get_p(board, x, cur_y)
        if p and p.piece_type == chess.QUEEN:
            return 1
    return 0


def winnable_total_mg(board: chess.Board, v: Optional[int] = None) -> int:
    if v is None:
        v = middle_game_evaluation(board, True)
    sign = 1 if v > 0 else (-1 if v < 0 else 0)
    return sign * max(min(winnable(board) + 50, 0), -abs(v))


def winnable_total_eg(board: chess.Board, v: Optional[int] = None) -> int:
    if v is None:
        v = end_game_evaluation(board, True)
    sign = 1 if v > 0 else (-1 if v < 0 else 0)
    return sign * max(winnable(board), -abs(v))


@sum_over_squares
def flank_attack(board: chess.Board, sq: chess.Square) -> int:
    x, y = get_x(sq), get_y(sq)
    if y > 4:
        return 0
    for tx in range(8):
        for ty in range(8):
            if is_black(get_p(board, tx, ty), chess.KING):
                if tx == 0 and x > 2:
                    return 0
                if tx < 3 and x > 3:
                    return 0
                if tx >= 3 and tx < 5 and (x < 2 or x > 5):
                    return 0
                if tx >= 5 and x < 4:
                    return 0
                if tx == 7 and x < 5:
                    return 0
    a = attack(board, sq)
    if not a:
        return 0
    return 2 if a > 1 else 1


@sum_over_squares
def flank_defense(board: chess.Board, sq: chess.Square) -> int:
    x, y = get_x(sq), get_y(sq)
    if y > 4:
        return 0
    for tx in range(8):
        for ty in range(8):
            if is_black(get_p(board, tx, ty), chess.KING):
                if tx == 0 and x > 2:
                    return 0
                if tx < 3 and x > 3:
                    return 0
                if tx >= 3 and tx < 5 and (x < 2 or x > 5):
                    return 0
                if tx >= 5 and x < 4:
                    return 0
                if tx == 7 and x < 5:
                    return 0
    return 1 if attack(board.mirror(), make_sq(x, 7 - y)) > 0 else 0


def king_danger(board: chess.Board) -> int:
    count = king_attackers_count(board)
    weight = king_attackers_weight(board)
    kingAttacks = king_attacks(board)
    weak = weak_bonus(board)
    unsafeChecks = unsafe_checks(board)
    blockersForKing = blockers_for_king(board)
    kingFlankAttack = flank_attack(board)
    kingFlankDefense = flank_defense(board)
    noQueen = 0 if queen_count(board) > 0 else 1
    v = (
        count * weight
        + 69 * kingAttacks
        + 185 * weak
        - 100 * (1 if knight_defender(board.mirror()) > 0 else 0)
        + 148 * unsafeChecks
        + 98 * blockersForKing
        - 4 * kingFlankDefense
        + int(3 * kingFlankAttack * kingFlankAttack / 8)
        - 873 * noQueen
        - int(6 * (shelter_strength(board) - shelter_storm(board)) / 8)
        + mobility_mg(board)
        - mobility_mg(board.mirror())
        + 37
        + int(772 * min(safe_check(board, None, 3), 1.45))
        + int(1084 * min(safe_check(board, None, 2), 1.75))
        + int(645 * min(safe_check(board, None, 1), 1.50))
        + int(792 * min(safe_check(board, None, 0), 1.62))
    )
    if v > 100:
        return v
    return 0


def king_mg(board: chess.Board) -> int:
    kd = king_danger(board)
    v = (
        -shelter_strength(board)
        + shelter_storm(board)
        + int(kd * kd / 4096)
        + 8 * flank_attack(board)
        + 17 * pawnless_flank(board)
    )
    return v


def king_eg(board: chess.Board) -> int:
    return (
        -16 * king_pawn_distance(board)
        + endgame_shelter(board)
        + 95 * pawnless_flank(board)
        + int(king_danger(board) / 16)
    )


@sum_over_squares
def weak_queen_protection(board: chess.Board, sq: chess.Square) -> int:
    if not weak_enemies(board, sq):
        return 0
    if not queen_attack(board.mirror(), make_sq(get_x(sq), 7 - get_y(sq))):
        return 0
    return 1


def threats_mg(board: chess.Board) -> int:
    v = (
        69 * hanging(board)
        + (24 if king_threat(board) > 0 else 0)
        + 48 * pawn_push_threat(board)
        + 173 * threat_safe_pawn(board)
        + 60 * slider_on_queen(board)
        + 16 * knight_on_queen(board)
        + 7 * restricted(board)
        + 14 * weak_queen_protection(board)
    )
    for x in range(8):
        for y in range(8):
            s = make_sq(x, y)
            v += [0, 5, 57, 77, 88, 79, 0][minor_threat(board, s)]
            v += [0, 3, 37, 42, 0, 58, 0][rook_threat(board, s)]
    return v


def threats_eg(board: chess.Board) -> int:
    v = (
        36 * hanging(board)
        + (89 if king_threat(board) > 0 else 0)
        + 39 * pawn_push_threat(board)
        + 94 * threat_safe_pawn(board)
        + 18 * slider_on_queen(board)
        + 11 * knight_on_queen(board)
        + 7 * restricted(board)
    )
    for x in range(8):
        for y in range(8):
            s = make_sq(x, y)
            v += [0, 32, 41, 56, 119, 161, 0][minor_threat(board, s)]
            v += [0, 46, 68, 60, 38, 41, 0][rook_threat(board, s)]
    return v


@sum_over_squares
def passed_leverable(board: chess.Board, sq: chess.Square) -> int:
    if not candidate_passed(board, sq):
        return 0
    x, y = get_x(sq), get_y(sq)
    if not is_black(get_p(board, x, y - 1), chess.PAWN):
        return 1
    pos2 = board.mirror()
    for i in [-1, 1]:
        s1 = make_sq(x + i, y)
        s2 = make_sq(x + i, 7 - y)
        if (
            is_white(get_p(board, x + i, y + 1), chess.PAWN)
            and not is_black(get_p(board, x + i, y))
            and (attack(board, s1) > 0 or attack(pos2, s2) <= 1)
        ):
            return 1
    return 0


@sum_over_squares
def passed_mg(board: chess.Board, sq: chess.Square) -> int:
    if not passed_leverable(board, sq):
        return 0
    return (
        [0, 10, 17, 15, 62, 168, 276][passed_rank(board, sq)]
        + passed_block(board, sq)
        - 11 * passed_file(board, sq)
    )


@sum_over_squares
def passed_eg(board: chess.Board, sq: chess.Square) -> int:
    if not passed_leverable(board, sq):
        return 0
    return (
        king_proximity(board, sq)
        + [0, 28, 33, 41, 72, 177, 260][passed_rank(board, sq)]
        + passed_block(board, sq)
        - 8 * passed_file(board, sq)
    )


@sum_over_squares
def piece_count(board: chess.Board, sq: chess.Square) -> int:
    return 1 if is_white(get_p(board, get_x(sq), get_y(sq))) else 0


@sum_over_squares
def bishop_xray_pawns(board: chess.Board, sq: chess.Square) -> int:
    x, y = get_x(sq), get_y(sq)
    if not is_white(get_p(board, x, y), chess.BISHOP):
        return 0
    count = 0
    for tx in range(8):
        for ty in range(8):
            if is_black(get_p(board, tx, ty), chess.PAWN) and abs(x - tx) == abs(
                y - ty
            ):
                count += 1
    return count


@sum_over_squares
def rook_on_king_ring(board: chess.Board, sq: chess.Square) -> int:
    x, y = get_x(sq), get_y(sq)
    if not is_white(get_p(board, x, y), chess.ROOK):
        return 0
    if king_attackers_count(board, sq) > 0:
        return 0
    for ty in range(8):
        if king_ring(board, make_sq(x, ty)):
            return 1
    return 0


@sum_over_squares
def bishop_on_king_ring(board: chess.Board, sq: chess.Square) -> int:
    x, y = get_x(sq), get_y(sq)
    if not is_white(get_p(board, x, y), chess.BISHOP):
        return 0
    if king_attackers_count(board, sq) > 0:
        return 0
    for i in range(4):
        ix = int(i > 1) * 2 - 1
        iy = int(i % 2 == 0) * 2 - 1
        for d in range(1, 8):
            nx, ny = x + d * ix, y + d * iy
            if not (0 <= nx <= 7 and 0 <= ny <= 7):
                break
            if king_ring(board, make_sq(nx, ny)):
                return 1
            if get_p(board, nx, ny) and get_p(board, nx, ny).piece_type == chess.PAWN:
                break
    return 0


@sum_over_squares
def queen_infiltration(board: chess.Board, sq: chess.Square) -> int:
    x, y = get_x(sq), get_y(sq)
    if not is_white(get_p(board, x, y), chess.QUEEN):
        return 0
    if y > 3:
        return 0
    if is_black(get_p(board, x + 1, y - 1), chess.PAWN) or is_black(
        get_p(board, x - 1, y - 1), chess.PAWN
    ):
        return 0
    if pawn_attacks_span(board, sq):
        return 0
    return 1


@sum_over_squares
def pieces_mg(board: chess.Board, sq: chess.Square) -> int:
    p = get_p(board, get_x(sq), get_y(sq))
    if not is_white(p) or p.piece_type in (chess.KING, chess.PAWN):
        return 0
    v = (
        [0, 31, -7, 30, 56][outpost_total(board, sq)]
        + 18 * minor_behind_pawn(board, sq)
        - 3 * bishop_pawns(board, sq)
        - 4 * bishop_xray_pawns(board, sq)
        + 6 * rook_on_queen_file(board, sq)
        + 16 * rook_on_king_ring(board, sq)
        + 24 * bishop_on_king_ring(board, sq)
        + [0, 19, 48][rook_on_file(board, sq)]
        - trapped_rook(board, sq)
        * 55
        * (1 if board.has_castling_rights(chess.WHITE) else 2)
        - 56 * weak_queen(board, sq)
        - 2 * queen_infiltration(board, sq)
        - (8 if p.piece_type == chess.KNIGHT else 6) * king_protector(board, sq)
        + 45 * long_diagonal_bishop(board, sq)
    )
    return v


@sum_over_squares
def pieces_eg(board: chess.Board, sq: chess.Square) -> int:
    p = get_p(board, get_x(sq), get_y(sq))
    if not is_white(p) or p.piece_type in (chess.KING, chess.PAWN):
        return 0
    v = (
        [0, 22, 36, 23, 36][outpost_total(board, sq)]
        + 3 * minor_behind_pawn(board, sq)
        - 7 * bishop_pawns(board, sq)
        - 5 * bishop_xray_pawns(board, sq)
        + 11 * rook_on_queen_file(board, sq)
        + [0, 7, 29][rook_on_file(board, sq)]
        - trapped_rook(board, sq)
        * 13
        * (1 if board.has_castling_rights(chess.WHITE) else 2)
        - 15 * weak_queen(board, sq)
        + 14 * queen_infiltration(board, sq)
        - 9 * king_protector(board, sq)
    )
    return v


@sum_over_squares
def blocked(board: chess.Board, sq: chess.Square) -> int:
    x, y = get_x(sq), get_y(sq)
    if not is_white(get_p(board, x, y), chess.PAWN):
        return 0
    if y != 2 and y != 3:
        return 0
    if not is_black(get_p(board, x, y - 1), chess.PAWN):
        return 0
    return 4 - y


@sum_over_squares
def pawn_attacks_span(board: chess.Board, sq: chess.Square) -> int:
    x, y = get_x(sq), get_y(sq)
    pos2 = board.mirror()
    for cur_y in range(y):
        if is_black(get_p(board, x - 1, cur_y), chess.PAWN) and (
            cur_y == y - 1
            or (
                not is_white(get_p(board, x - 1, cur_y + 1), chess.PAWN)
                and not backward(pos2, make_sq(x - 1, 7 - cur_y))
            )
        ):
            return 1
        if is_black(get_p(board, x + 1, cur_y), chess.PAWN) and (
            cur_y == y - 1
            or (
                not is_white(get_p(board, x + 1, cur_y + 1), chess.PAWN)
                and not backward(pos2, make_sq(x + 1, 7 - cur_y))
            )
        ):
            return 1
    return 0


@sum_over_squares
def doubled_isolated(board: chess.Board, sq: chess.Square) -> int:
    x, y = get_x(sq), get_y(sq)
    if not is_white(get_p(board, x, y), chess.PAWN):
        return 0
    if isolated(board, sq):
        obe = eop = ene = 0
        for cur_y in range(8):
            if cur_y > y and is_white(get_p(board, x, cur_y), chess.PAWN):
                obe += 1
            if cur_y < y and is_black(get_p(board, x, cur_y), chess.PAWN):
                eop += 1
            if is_black(get_p(board, x - 1, cur_y), chess.PAWN) or is_black(
                get_p(board, x + 1, cur_y), chess.PAWN
            ):
                ene += 1
        if obe > 0 and ene == 0 and eop > 0:
            return 1
    return 0


@sum_over_squares
def pawns_mg(board: chess.Board, sq: chess.Square) -> int:
    v = 0
    if doubled_isolated(board, sq):
        v -= 11
    elif isolated(board, sq):
        v -= 5
    elif backward(board, sq):
        v -= 9
    v -= doubled(board, sq) * 11
    v += connected_bonus(board, sq) if connected(board, sq) else 0
    v -= 13 * weak_unopposed_pawn(board, sq)
    v += [0, -11, -3][blocked(board, sq)]
    return v


@sum_over_squares
def pawns_eg(board: chess.Board, sq: chess.Square) -> int:
    v = 0
    if doubled_isolated(board, sq):
        v -= 56
    elif isolated(board, sq):
        v -= 15
    elif backward(board, sq):
        v -= 24
    v -= doubled(board, sq) * 56
    v += (
        int(connected_bonus(board, sq) * (rank(board, sq) - 3) / 4)
        if connected(board, sq)
        else 0
    )
    v -= 27 * weak_unopposed_pawn(board, sq)
    v -= 56 * weak_lever(board, sq)
    v += [0, -4, 4][blocked(board, sq)]
    return v


def rule50(board: chess.Board, sq: Optional[chess.Square] = None) -> int:
    if sq is not None:
        return 0
    return board.halfmove_clock


functions = [
    main_evaluation,
    isolated,
    opposed,
    rank,
    file,
    phalanx,
    supported,
    backward,
    doubled,
    connected,
    middle_game_evaluation,
    end_game_evaluation,
    scale_factor,
    phase,
    imbalance,
    bishop_count,
    bishop_pair,
    pinned_direction,
    mobility,
    mobility_area,
    mobility_bonus,
    knight_attack,
    bishop_xray_attack,
    rook_xray_attack,
    queen_attack,
    outpost,
    outpost_square,
    reachable_outpost,
    minor_behind_pawn,
    bishop_pawns,
    rook_on_file,
    trapped_rook,
    weak_queen,
    space_area,
    pawn_attack,
    king_attack,
    attack,
    non_pawn_material,
    safe_pawn,
    threat_safe_pawn,
    weak_enemies,
    minor_threat,
    rook_threat,
    hanging,
    king_threat,
    pawn_push_threat,
    candidate_passed,
    king_proximity,
    passed_block,
    passed_file,
    passed_rank,
    pawnless_flank,
    strength_square,
    storm_square,
    shelter_strength,
    shelter_storm,
    king_pawn_distance,
    check_attack,
    safe_check,
    queen_count,
    king_attackers_count,
    king_attackers_weight,
    king_attacks,
    weak_bonus,
    weak_squares,
    winnable,
    unsafe_checks,
    tempo,
    pawn_count,
    connected_bonus,
    mobility_mg,
    mobility_eg,
    piece_value_bonus,
    psqt_bonus,
    piece_value_mg,
    piece_value_eg,
    psqt_mg,
    psqt_eg,
    king_protector,
    knight_count,
    imbalance_total,
    weak_unopposed_pawn,
    rook_count,
    opposite_bishops,
    king_distance,
    long_diagonal_bishop,
    queen_attack_diagonal,
    pinned,
    king_ring,
    slider_on_queen,
    knight_on_queen,
    outpost_total,
    restricted,
    knight_defender,
    endgame_shelter,
    space,
    weak_lever,
    blockers_for_king,
    rook_on_queen_file,
    winnable_total_mg,
    winnable_total_eg,
    flank_attack,
    flank_defense,
    king_danger,
    king_mg,
    king_eg,
    weak_queen_protection,
    threats_mg,
    threats_eg,
    passed_leverable,
    passed_mg,
    passed_eg,
    piece_count,
    bishop_xray_pawns,
    rook_on_king_ring,
    bishop_on_king_ring,
    queen_infiltration,
    pieces_mg,
    pieces_eg,
    blocked,
    pawn_attacks_span,
    doubled_isolated,
    pawns_mg,
    pawns_eg,
    rule50,
]
