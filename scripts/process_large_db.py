import sys
import os
sys.path.append(os.getcwd())

import chess.pgn
import csv
import multiprocessing
import subprocess
from tqdm import tqdm
from xpl.evaluation import functions

# Import logic from generate_dataset (since it's in the same folder, we can import if we add to path)
# Or we can just re-patch here to be safe and self-contained
import chess

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
    game_id, move_idx, move_san, fen = args
    board = chess.Board(fen)
    mirrored_board = board.mirror()
    
    row = {
        'game_id': game_id,
        'move_number': move_idx,
        'move_san': move_san,
        'fen': fen
    }
    
    for f in functions:
        name = f.__name__
        try:
            val = f(board)
            row[name] = val
            if name in SYMMETRIC_EQUAL:
                row[name + "_flipped"] = val
            elif name in SYMMETRIC_NEGATIVE:
                row[name + "_flipped"] = -val if isinstance(val, (int, float)) else val
            else:
                row[name + "_flipped"] = f(mirrored_board)
        except Exception as e:
            if isinstance(e, KeyboardInterrupt): exit()
            row[name] = f"Error: {e}"
            row[name + "_flipped"] = f"Error: {e}"
    return row

def download_and_unpack():
    url = "https://database.lichess.org/standard/lichess_db_standard_rated_2013-01.pgn.zst"
    zst_file = "data/lichess_db_2013-01.pgn.zst"
    pgn_file = "data/lichess_db_2013-01.pgn"
    
    os.makedirs("data", exist_ok=True)
    
    if not os.path.exists(pgn_file):
        if not os.path.exists(zst_file):
            print(f"Downloading {url}...")
            subprocess.run(["curl", "-o", zst_file, url], check=True)
        
        print(f"Unpacking {zst_file}...")
        # -d for decompress, --rm to remove source file after success (optional, but keep it for now)
        subprocess.run(["zstd", "-d", zst_file, "-o", pgn_file], check=True)
    else:
        print(f"{pgn_file} already exists, skipping download.")
    
    return pgn_file

import argparse

def main():
    parser = argparse.ArgumentParser(description="Process Lichess DB with sharding.")
    parser.add_argument("--num-games", type=int, default=3000, help="Total games to process across all shards")
    parser.add_argument("--shard-id", type=int, default=0, help="Current shard index (0-indexed)")
    parser.add_argument("--num-shards", type=int, default=1, help="Total number of shards")
    parser.add_argument("--output-dir", type=str, default=".", help="Directory for output")
    args_cli = parser.parse_args()

    pgn_path = download_and_unpack()
    
    # Calculate shard range
    games_per_shard = args_cli.num_games // args_cli.num_shards
    start_game = args_cli.shard_id * games_per_shard
    # Last shard takes any remainder
    if args_cli.shard_id == args_cli.num_shards - 1:
        end_game = args_cli.num_games
    else:
        end_game = (args_cli.shard_id + 1) * games_per_shard
    
    output_path = os.path.join(args_cli.output_dir, f"shard_{args_cli.shard_id}.csv")
    os.makedirs(args_cli.output_dir, exist_ok=True)

    tasks = []
    print(f"Shard {args_cli.shard_id}/{args_cli.num_shards}: Extracting games {start_game} to {end_game}...")
    
    with open(pgn_path) as pgn:
        # Skip games before our shard
        for _ in range(start_game):
            if not chess.pgn.skip_game(pgn):
                break
        
        for i in range(start_game, end_game):
            game = chess.pgn.read_game(pgn)
            if game is None:
                break
            
            game_id = i + 1
            board = game.board()
            for move_idx, move in enumerate(game.mainline_moves(), 1):
                move_san = board.san(move)
                board.push(move)
                tasks.append((game_id, move_idx, move_san, board.fen()))

    cpus = os.cpu_count()
    print(f"Processing {len(tasks)} positions with {cpus} cores...")
    
    fieldnames = ['game_id', 'move_number', 'move_san', 'fen']
    for f in functions:
        fieldnames.append(f.__name__)
        fieldnames.append(f.__name__ + "_flipped")

    print(f"Streaming results to {output_path}...")
    with open(output_path, 'w', newline='') as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        
        with multiprocessing.Pool(processes=cpus) as pool:
            for result in tqdm(pool.imap(evaluate_position, tasks, chunksize=100), total=len(tasks), desc=f"Shard {args_cli.shard_id}"):
                writer.writerow(result)
                if result['move_number'] % 100 == 0:
                    csv_file.flush()
    
    print(f"Shard {args_cli.shard_id} done!")

if __name__ == "__main__":
    main()
