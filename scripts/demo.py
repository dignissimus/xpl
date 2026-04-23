import csv
import chess
import os

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def print_board(fen):
    board = chess.Board(fen)
    print(board)
    print("\nFEN:", fen)

def run_demo(csv_path):
    if not os.path.exists(csv_path):
        print(f"Error: {csv_path} not found. Run generate_dataset.py first.")
        return

    data = []
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            data.append(row)

    current_idx = 0
    total_moves = len(data)

    metrics_to_show = [
        'main_evaluation', 'middle_game_evaluation', 'end_game_evaluation',
        'mobility', 'king_danger', 'passed_mg', 'pieces_mg'
    ]

    while True:
        clear_screen()
        row = data[current_idx]
        
        print(f"Move {row['move_number']}/{total_moves}: {row['move_san']}")
        print("=" * 30)
        print_board(row['fen'])
        print("=" * 30)
        print("METRICS:")
        
        board = chess.Board(row['fen'])
        current_player = "White" if board.turn == chess.WHITE else "Black"
        print(f"To move: {current_player}")
        print("-" * 30)

        for metric in metrics_to_show:
            val = row.get(metric, "N/A")
            flipped_val = row.get(f"{metric}_flipped", "N/A")
            print(f"{metric:25} | Normal: {val:<8} | Flipped: {flipped_val}")
        
        print("-" * 30)
        print("\nCommands: [n]ext, [p]revious, [q]uit, [move_number]")
        cmd = input("\nEnter command: ").strip().lower()

        if cmd == 'q':
            break
        elif cmd == 'n':
            if current_idx < total_moves - 1:
                current_idx += 1
        elif cmd == 'p':
            if current_idx > 0:
                current_idx -= 1
        elif cmd.isdigit():
            move_num = int(cmd)
            if 1 <= move_num <= total_moves:
                current_idx = move_num - 1
        else:
            input("Invalid command. Press Enter to continue...")

if __name__ == "__main__":
    run_demo("game_metrics.csv")
