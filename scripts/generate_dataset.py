import chess.pgn
import csv
from xpl.evaluation import functions
import os
from tqdm import tqdm
import multiprocessing
import argparse

# Ad-hoc patch to cache FEN, transposition key, and mirror generation
_orig_fen = chess.Board.fen
_orig_tkey = chess.Board._transposition_key
_orig_mirror = chess.Board.mirror
_orig_push = chess.Board.push
_orig_pop = chess.Board.pop
_orig_set_fen = chess.Board.set_fen

def patched_tkey(self):
    if not hasattr(self, "_cached_tkey"):
        self._cached_tkey = _orig_tkey(self)
    return self._cached_tkey

def patched_fen(self):
    if not hasattr(self, "_cached_fen"):
        self._cached_fen = _orig_fen(self)
    return self._cached_fen

def patched_mirror(self):
    if not hasattr(self, "_cached_mirror"):
        self._cached_mirror = _orig_mirror(self)
    return self._cached_mirror

def clear_board_cache(self):
    if hasattr(self, "_cached_tkey"): delattr(self, "_cached_tkey")
    if hasattr(self, "_cached_fen"): delattr(self, "_cached_fen")
    if hasattr(self, "_cached_mirror"): delattr(self, "_cached_mirror")

def patched_push(self, move):
    clear_board_cache(self)
    return _orig_push(self, move)

def patched_pop(self):
    clear_board_cache(self)
    return _orig_pop(self)

def patched_set_fen(self, fen):
    clear_board_cache(self)
    return _orig_set_fen(self, fen)

chess.Board._transposition_key = patched_tkey
chess.Board.fen = patched_fen
chess.Board.mirror = patched_mirror
chess.Board.push = patched_push
chess.Board.pop = patched_pop
chess.Board.set_fen = patched_set_fen

SYMMETRIC_EQUAL = [
    'opposed', 'rank', 'file', 'doubled', 'scale_factor', 'phase', 
    'king_attack', 'pawnless_flank', 'king_pawn_distance', 'winnable', 
    'rook_count', 'opposite_bishops', 'endgame_shelter', 'weak_lever', 
    'winnable_total_mg', 'bishop_on_king_ring', 'doubled_isolated', 'rule50'
]
SYMMETRIC_NEGATIVE = [
    'main_evaluation', 'middle_game_evaluation', 'end_game_evaluation', 
    'tempo', 'imbalance_total', 'winnable_total_eg'
]

def evaluate_position(args):
    move_idx, move_san, fen = args
    board = chess.Board(fen)
    mirrored_board = board.mirror()
    
    row = {
        'move_number': move_idx,
        'move_san': move_san,
        'fen': fen
    }
    
    for f in functions:
        name = f.__name__
        try:
            # Evaluate normal state
            val = f(board)
            row[name] = val
            
            # Optimized evaluation for flipped state
            if name in SYMMETRIC_EQUAL:
                row[name + "_flipped"] = val
            elif name in SYMMETRIC_NEGATIVE:
                row[name + "_flipped"] = -val if isinstance(val, (int, float)) else val
            else:
                row[name + "_flipped"] = f(mirrored_board)
        except Exception as e:
            if isinstance(e, KeyboardInterrupt):
                exit()
                
            row[name] = f"Error: {e}"
            row[name + "_flipped"] = f"Error: {e}"
    return row

def generate_csv(pgn_path, csv_path, single_core=False):
    if not os.path.exists(pgn_path):
        print(f"Error: {pgn_path} not found.")
        return

    with open(pgn_path) as pgn_file:
        game = chess.pgn.read_game(pgn_file)
    
    if game is None:
        print("Error: No game found in PGN.")
        return

    board = game.board()
    tasks = []
    
    # Pre-generate all board states
    moves = list(game.mainline_moves())
    for idx, move in enumerate(moves, 1):
        move_san = board.san(move)
        board.push(move)
        tasks.append((idx, move_san, board.fen()))

    if single_core:
        print("Running in single-core mode (no multiprocessing)...")
        results = []
        for task in tqdm(tasks, desc="Processing moves"):
            results.append(evaluate_position(task))
    else:
        cpus = os.cpu_count()
        print(f"Starting multiprocessing with {cpus} cores...")
        with multiprocessing.Pool(processes=cpus) as pool:
            results = list(tqdm(pool.imap(evaluate_position, tasks), total=len(tasks), desc="Processing moves"))

    # Header
    fieldnames = ['move_number', 'move_san', 'fen']
    for f in functions:
        fieldnames.append(f.__name__)
        fieldnames.append(f.__name__ + "_flipped")

    with open(csv_path, 'w', newline='') as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)
    
    print(f"Dataset created: {csv_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate chess evaluation dataset from PGN.")
    parser.add_argument("--pgn", default="data/game.pgn", help="Path to PGN file")
    parser.add_argument("--output", default="game_metrics.csv", help="Path to output CSV")
    parser.add_argument("--single-core", action="store_true", help="Use only one core and avoid multiprocessing")
    
    args = parser.parse_args()
    generate_csv(args.pgn, args.output, single_core=args.single_core)
