#!/usr/bin/env python3
"""
🕹️ 8-BIT RETRO TERMINAL ARCADE (12-IN-1 RETRO SUITE)
100% Offline • Zero External Dependencies • Pure Python & ANSI
Games:
  1. 🐍 Snake         2. 🏓 Pong          3. 🚀 Galactica      4. 🧱 Breakout
  5. 🧩 Tetris        6. 🐦 Flappy Bird   7. 🟡 Pac-Maze       8. 🐸 Frogger
  9. ☄️ Asteroids    10. 🗡️ Mini-Rogue   11. 🔢 2048          12. 💣 Minesweeper
"""
import atexit
import json
import math
import os
import random
import sys
import time
from pathlib import Path

# Force UTF-8 encoding on standard streams to avoid Windows cp1252 charmap errors
try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stdin, "reconfigure"):
        sys.stdin.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# Enable ANSI escape sequences & handle platform keyboard input
if os.name == "nt":
    os.system("")
    import msvcrt
else:
    import select
    import termios
    import tty
    try:
        if sys.stdin.isatty():
            _old_term_attr = termios.tcgetattr(sys.stdin)
            tty.setcbreak(sys.stdin.fileno())
            atexit.register(lambda: termios.tcsetattr(sys.stdin, termios.TCSADRAIN, _old_term_attr))
    except Exception:
        pass

SCORE_FILE = Path(__file__).resolve().parent / "arcade_scores.json"

# ANSI Colors & Styles
C_RESET = "\033[0m"
C_BOLD = "\033[1m"
C_DIM = "\033[2m"
C_RED = "\033[91m"
C_GREEN = "\033[92m"
C_YELLOW = "\033[93m"
C_BLUE = "\033[94m"
C_MAGENTA = "\033[95m"
C_CYAN = "\033[96m"
C_WHITE = "\033[97m"
C_GRAY = "\033[90m"
BG_BLUE = "\033[44m"
BG_DARK = "\033[40m"


def clear_screen():
    sys.stdout.write("\033[2J\033[H")
    sys.stdout.flush()


def hide_cursor():
    sys.stdout.write("\033[?25l")
    sys.stdout.flush()


def show_cursor():
    sys.stdout.write("\033[?25h\033[0m")
    sys.stdout.flush()


atexit.register(show_cursor)


def load_scores():
    try:
        if SCORE_FILE.exists():
            with open(SCORE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def save_score(game, score):
    scores = load_scores()
    if score > scores.get(game, 0):
        scores[game] = score
        try:
            with open(SCORE_FILE, "w", encoding="utf-8") as f:
                json.dump(scores, f)
        except Exception:
            pass
    return scores.get(game, 0)


def get_key():
    """Non-blocking keyboard input. Returns lowercase key name or None."""
    if os.name == "nt":
        if msvcrt.kbhit():
            ch = msvcrt.getch()
            # Windows Virtual Key prefix (arrows, function keys)
            if ch in (b"\x00", b"\xe0"):
                ch2 = msvcrt.getch()
                return {b"H": "up", b"P": "down", b"K": "left", b"M": "right"}.get(ch2)
            # ANSI escape sequence (e.g. \x1b[A for arrow keys in modern emulators / ConPTY)
            if ch == b"\x1b":
                time.sleep(0.005)
                if msvcrt.kbhit():
                    ch2 = msvcrt.getch()
                    if ch2 == b"[" and msvcrt.kbhit():
                        ch3 = msvcrt.getch()
                        return {b"A": "up", b"B": "down", b"C": "right", b"D": "left"}.get(ch3, "escape")
                return "escape"
            if ch in (b"\r", b"\n"):
                return "enter"
            if ch == b" ":
                return " "
            try:
                char = ch.decode("utf-8", "ignore").lower()
                if char in ("\r", "\n"):
                    return "enter"
                return char
            except Exception:
                return None
        return None
    else:
        dr, _, _ = select.select([sys.stdin], [], [], 0)
        if dr:
            ch = sys.stdin.read(1)
            if ch == "\x1b":
                dr2, _, _ = select.select([sys.stdin], [], [], 0.05)
                if dr2:
                    seq = sys.stdin.read(2)
                    return {"[A": "up", "[B": "down", "[C": "right", "[D": "left"}.get(seq, "escape")
                return "escape"
            if ch in ("\r", "\n"):
                return "enter"
            return ch.lower()
        return None


def game_over_screen(title, score, high_score):
    sys.stdout.write(f"\n  {C_RED}{C_BOLD}{title}!{C_RESET} Score: {score}  Best: {max(score, high_score)}  (Press any key to return to menu)")
    sys.stdout.flush()
    while True:
        k = get_key()
        if k is not None:
            break
        time.sleep(0.05)


# ==============================================================================
# GAME 1: 🐍 SNAKE
# ==============================================================================
def play_snake():
    WIDTH, HEIGHT = 46, 20
    snake = [(WIDTH // 2, HEIGHT // 2), (WIDTH // 2 - 1, HEIGHT // 2), (WIDTH // 2 - 2, HEIGHT // 2)]
    direction = "right"
    next_dir = "right"

    def spawn_food():
        while True:
            pos = (random.randint(1, WIDTH - 2), random.randint(1, HEIGHT - 2))
            if pos not in snake:
                return pos

    food = spawn_food()
    score = 0
    high_score = load_scores().get("snake", 0)
    speed = 0.09
    game_over = False

    hide_cursor()
    clear_screen()

    while not game_over:
        k = get_key()
        if k in ("q", "escape"):
            return
        elif k in ("up", "w") and direction != "down":
            next_dir = "up"
        elif k in ("down", "s") and direction != "up":
            next_dir = "down"
        elif k in ("left", "a") and direction != "right":
            next_dir = "left"
        elif k in ("right", "d") and direction != "left":
            next_dir = "right"

        direction = next_dir
        hx, hy = snake[0]
        if direction == "up":
            hy -= 1
        elif direction == "down":
            hy += 1
        elif direction == "left":
            hx -= 1
        elif direction == "right":
            hx += 1

        if hx <= 0 or hx >= WIDTH - 1 or hy <= 0 or hy >= HEIGHT - 1 or (hx, hy) in snake:
            game_over = True
            break

        snake.insert(0, (hx, hy))
        if (hx, hy) == food:
            score += 10
            food = spawn_food()
            speed = max(0.04, speed * 0.98)
        else:
            snake.pop()

        grid = [[" " for _ in range(WIDTH)] for _ in range(HEIGHT)]
        for x in range(WIDTH):
            grid[0][x] = "═"
            grid[HEIGHT - 1][x] = "═"
        for y in range(HEIGHT):
            grid[y][0] = "║"
            grid[y][WIDTH - 1] = "║"
        grid[0][0] = "╔"
        grid[0][WIDTH - 1] = "╗"
        grid[HEIGHT - 1][0] = "╚"
        grid[HEIGHT - 1][WIDTH - 1] = "╝"

        fx, fy = food
        grid[fy][fx] = f"{C_RED}●{C_RESET}"

        for i, (sx, sy) in enumerate(snake):
            if i == 0:
                grid[sy][sx] = f"{C_GREEN}{C_BOLD}●{C_RESET}"
            else:
                grid[sy][sx] = f"{C_GREEN}o{C_RESET}"

        frame = [f"\033[H{C_CYAN}╔═[ 🐍 SNAKE 8-BIT ]═══════════════════════════════╗{C_RESET}",
                 f"  {C_YELLOW}Score: {score:04d}{C_RESET}   {C_MAGENTA}High: {max(high_score, score):04d}{C_RESET}   {C_GRAY}(WASD / Arrows to steer · Q to quit){C_RESET}"]
        for row in grid:
            frame.append(f"  {C_CYAN}" + "".join(row) + C_RESET)
        sys.stdout.write("\n".join(frame) + "\n")
        sys.stdout.flush()
        time.sleep(speed)

    save_score("snake", score)
    game_over_screen("GAME OVER", score, high_score)


# ==============================================================================
# GAME 2: 🏓 PONG
# ==============================================================================
def play_pong():
    WIDTH, HEIGHT = 54, 18
    p1_pos = HEIGHT // 2
    p2_pos = HEIGHT // 2
    pad_h = 4
    bx, by = WIDTH // 2, HEIGHT // 2
    vx, vy = random.choice([-1, 1]), random.choice([-0.6, 0.6])
    score_p1 = 0
    score_p2 = 0
    max_score = 5

    hide_cursor()
    clear_screen()

    while score_p1 < max_score and score_p2 < max_score:
        k = get_key()
        if k in ("q", "escape"):
            return
        elif k in ("up", "w") and p1_pos > 1:
            p1_pos -= 1
        elif k in ("down", "s") and p1_pos < HEIGHT - pad_h - 1:
            p1_pos += 1

        if random.random() < 0.85:
            if by < p2_pos + pad_h // 2 and p2_pos > 1:
                p2_pos -= 1
            elif by > p2_pos + pad_h // 2 and p2_pos < HEIGHT - pad_h - 1:
                p2_pos += 1

        bx += vx
        by += vy

        if by <= 1:
            by = 1
            vy = -vy
        elif by >= HEIGHT - 2:
            by = HEIGHT - 2
            vy = -vy

        if int(bx) == 2 and p1_pos <= int(by) < p1_pos + pad_h:
            vx = abs(vx) * 1.05
            vy += (int(by) - (p1_pos + pad_h / 2)) * 0.3
        elif int(bx) == WIDTH - 3 and p2_pos <= int(by) < p2_pos + pad_h:
            vx = -abs(vx) * 1.05
            vy += (int(by) - (p2_pos + pad_h / 2)) * 0.3

        if bx <= 0:
            score_p2 += 1
            bx, by = WIDTH // 2, HEIGHT // 2
            vx, vy = 1, random.choice([-0.6, 0.6])
            time.sleep(0.3)
        elif bx >= WIDTH - 1:
            score_p1 += 1
            bx, by = WIDTH // 2, HEIGHT // 2
            vx, vy = -1, random.choice([-0.6, 0.6])
            time.sleep(0.3)

        grid = [[" " for _ in range(WIDTH)] for _ in range(HEIGHT)]
        for x in range(WIDTH):
            grid[0][x] = "═"
            grid[HEIGHT - 1][x] = "═"
        for y in range(HEIGHT):
            grid[y][0] = "║"
            grid[y][WIDTH - 1] = "║"
            if y % 2 == 0 and 0 < y < HEIGHT - 1:
                grid[y][WIDTH // 2] = "┆"

        for i in range(pad_h):
            grid[p1_pos + i][2] = f"{C_CYAN}█{C_RESET}"
            grid[p2_pos + i][WIDTH - 3] = f"{C_MAGENTA}█{C_RESET}"

        ibx, iby = max(1, min(WIDTH - 2, int(bx))), max(1, min(HEIGHT - 2, int(by)))
        grid[iby][ibx] = f"{C_YELLOW}●{C_RESET}"

        frame = [f"\033[H{C_CYAN}╔═[ 🏓 RETRO PONG ]════════════════════════════════════╗{C_RESET}",
                 f"  {C_CYAN}YOU: {score_p1}{C_RESET}                      {C_MAGENTA}CPU: {score_p2}{C_RESET}     {C_GRAY}(First to 5 · W/S to move · Q to quit){C_RESET}"]
        for row in grid:
            frame.append("  " + "".join(row))
        sys.stdout.write("\n".join(frame) + "\n")
        sys.stdout.flush()
        time.sleep(0.04)

    save_score("pong", score_p1)
    msg = f"{C_GREEN}YOU WON! 🎉{C_RESET}" if score_p1 >= max_score else f"{C_RED}CPU WON! 🤖{C_RESET}"
    game_over_screen(msg, score_p1, load_scores().get("pong", 0))


# ==============================================================================
# GAME 3: 🚀 GALACTICA
# ==============================================================================
def play_galactica():
    WIDTH, HEIGHT = 50, 20
    player_x = WIDTH // 2
    bullets = []
    alien_bombs = []
    aliens = []
    lives = 3
    score = 0
    high_score = load_scores().get("galactica", 0)

    for row in range(3):
        for col in range(8):
            aliens.append({"x": col * 5 + 6, "y": row * 2 + 2, "type": row})

    fleet_dir = 1
    fleet_speed = 0.5
    last_fleet_move = time.time()
    last_shot = 0

    hide_cursor()
    clear_screen()

    while lives > 0 and aliens:
        now = time.time()
        k = get_key()
        if k in ("q", "escape"):
            return
        elif k in ("left", "a") and player_x > 2:
            player_x -= 2
        elif k in ("right", "d") and player_x < WIDTH - 4:
            player_x += 2
        elif k in (" ", "up", "w", "enter") and now - last_shot > 0.22:
            bullets.append([player_x, HEIGHT - 3])
            last_shot = now

        new_bullets = []
        for bx, by in bullets:
            by -= 1
            hit = False
            for a in list(aliens):
                if a["x"] <= bx <= a["x"] + 2 and a["y"] == by:
                    aliens.remove(a)
                    score += 30 - a["type"] * 10
                    hit = True
                    break
            if not hit and by > 0:
                new_bullets.append([bx, by])
        bullets = new_bullets

        if random.random() < 0.12 and aliens:
            shooter = random.choice(aliens)
            alien_bombs.append([shooter["x"] + 1, shooter["y"] + 1])

        new_bombs = []
        for bx, by in alien_bombs:
            by += 1
            if by == HEIGHT - 2 and player_x - 1 <= bx <= player_x + 1:
                lives -= 1
                time.sleep(0.3)
            elif by < HEIGHT - 1:
                new_bombs.append([bx, by])
        alien_bombs = new_bombs

        if now - last_fleet_move > fleet_speed:
            last_fleet_move = now
            shift_down = False
            for a in aliens:
                if (fleet_dir == 1 and a["x"] >= WIDTH - 5) or (fleet_dir == -1 and a["x"] <= 2):
                    fleet_dir = -fleet_dir
                    shift_down = True
                    break
            for a in aliens:
                if shift_down:
                    a["y"] += 1
                    if a["y"] >= HEIGHT - 3:
                        lives = 0
                else:
                    a["x"] += fleet_dir
            fleet_speed = max(0.12, 0.5 - (24 - len(aliens)) * 0.015)

        grid = [[" " for _ in range(WIDTH)] for _ in range(HEIGHT)]
        for x in range(WIDTH):
            grid[0][x] = "═"
            grid[HEIGHT - 1][x] = "═"
        for y in range(HEIGHT):
            grid[y][0] = "║"
            grid[y][WIDTH - 1] = "║"

        for a in aliens:
            color = C_RED if a["type"] == 0 else (C_YELLOW if a["type"] == 1 else C_GREEN)
            sprite = "▼▼" if a["type"] == 0 else ("👾" if a["type"] == 1 else "><")
            ax, ay = int(a["x"]), int(a["y"])
            if 0 < ay < HEIGHT - 1 and 0 < ax < WIDTH - 2:
                grid[ay][ax] = f"{color}{sprite[0]}{C_RESET}"
                grid[ay][ax + 1] = f"{color}{sprite[1]}{C_RESET}"

        for bx, by in bullets:
            grid[by][bx] = f"{C_YELLOW}|{C_RESET}"
        for bx, by in alien_bombs:
            grid[by][bx] = f"{C_RED}*{C_RESET}"

        py = HEIGHT - 2
        grid[py][player_x - 1] = f"{C_CYAN}▲{C_RESET}"
        grid[py][player_x] = f"{C_WHITE}{C_BOLD}▲{C_RESET}"
        grid[py][player_x + 1] = f"{C_CYAN}▲{C_RESET}"

        hearts = f"{C_RED}{'❤ ' * lives}{C_RESET}"
        frame = [f"\033[H{C_CYAN}╔═[ 🚀 GALACTICA 8-BIT ]════════════════════════════╗{C_RESET}",
                 f"  {C_YELLOW}Score: {score:04d}{C_RESET}   {C_MAGENTA}High: {max(high_score, score):04d}{C_RESET}   Lives: {hearts}  {C_GRAY}(A/D: Move · Space: Fire){C_RESET}"]
        for row in grid:
            frame.append("  " + "".join(row))
        sys.stdout.write("\n".join(frame) + "\n")
        sys.stdout.flush()
        time.sleep(0.04)

    save_score("galactica", score)
    result = f"{C_GREEN}EARTH SAVED! 🎉{C_RESET}" if not aliens else f"{C_RED}EARTH INVADED! 👾{C_RESET}"
    game_over_screen(result, score, high_score)


# ==============================================================================
# GAME 4: 🧱 BREAKOUT
# ==============================================================================
def play_breakout():
    WIDTH, HEIGHT = 46, 20
    pad_w = 6
    pad_x = (WIDTH - pad_w) // 2
    bx, by = WIDTH // 2, HEIGHT - 4
    vx, vy = random.choice([0.8, -0.8]), -0.7
    lives = 3
    score = 0
    high_score = load_scores().get("breakout", 0)

    bricks = {}
    colors = [C_RED, C_MAGENTA, C_YELLOW, C_GREEN]
    for r in range(4):
        for c in range(1, (WIDTH - 2) // 4):
            bricks[(c * 4 - 2, r + 2)] = (colors[r], 40 - r * 10)

    hide_cursor()
    clear_screen()

    while lives > 0 and bricks:
        k = get_key()
        if k in ("q", "escape"):
            return
        elif k in ("left", "a") and pad_x > 1:
            pad_x -= 2
        elif k in ("right", "d") and pad_x < WIDTH - pad_w - 1:
            pad_x += 2

        bx += vx
        by += vy

        if bx <= 1:
            bx = 1
            vx = abs(vx)
        elif bx >= WIDTH - 2:
            bx = WIDTH - 2
            vx = -abs(vx)
        if by <= 1:
            by = 1
            vy = abs(vy)

        if int(by) == HEIGHT - 2 and pad_x <= int(bx) <= pad_x + pad_w:
            vy = -abs(vy)
            hit_offset = (bx - (pad_x + pad_w / 2)) / (pad_w / 2)
            vx = hit_offset * 1.2
            if abs(vx) < 0.3:
                vx = 0.5 if vx >= 0 else -0.5

        if by >= HEIGHT - 1:
            lives -= 1
            bx, by = pad_x + pad_w // 2, HEIGHT - 4
            vx, vy = random.choice([0.8, -0.8]), -0.7
            time.sleep(0.4)
            continue

        hit_b = None
        for (brx, bry), (bcol, bval) in list(bricks.items()):
            if bry == int(by) and brx <= int(bx) < brx + 4:
                hit_b = (brx, bry)
                score += bval
                vy = -vy
                break
        if hit_b:
            del bricks[hit_b]

        grid = [[" " for _ in range(WIDTH)] for _ in range(HEIGHT)]
        for x in range(WIDTH):
            grid[0][x] = "═"
            grid[HEIGHT - 1][x] = "═"
        for y in range(HEIGHT):
            grid[y][0] = "║"
            grid[y][WIDTH - 1] = "║"

        for (brick_x, brick_y), (bcolor, _) in bricks.items():
            for i in range(4):
                if brick_x + i < WIDTH - 1:
                    grid[brick_y][brick_x + i] = f"{bcolor}█{C_RESET}"

        for i in range(pad_w):
            if pad_x + i < WIDTH - 1:
                grid[HEIGHT - 2][pad_x + i] = f"{C_CYAN}▀{C_RESET}"

        if 0 < int(by) < HEIGHT - 1 and 0 < int(bx) < WIDTH - 1:
            grid[int(by)][int(bx)] = f"{C_WHITE}●{C_RESET}"

        hearts = f"{C_RED}{'❤ ' * lives}{C_RESET}"
        frame = [f"\033[H{C_CYAN}╔═[ 🧱 BREAKOUT 8-BIT ]═════════════════════════════╗{C_RESET}",
                 f"  {C_YELLOW}Score: {score:04d}{C_RESET}   {C_MAGENTA}High: {max(high_score, score):04d}{C_RESET}   Lives: {hearts}  {C_GRAY}(A/D to slide paddle){C_RESET}"]
        for row in grid:
            frame.append("  " + "".join(row))
        sys.stdout.write("\n".join(frame) + "\n")
        sys.stdout.flush()
        time.sleep(0.04)

    save_score("breakout", score)
    msg = f"{C_GREEN}BOARD CLEARED! 🏆{C_RESET}" if not bricks else f"{C_RED}GAME OVER!{C_RESET}"
    game_over_screen(msg, score, high_score)


# ==============================================================================
# GAME 5: 🧩 TETRIS
# ==============================================================================
def play_tetris():
    BOARD_W, BOARD_H = 10, 20
    board = [[None for _ in range(BOARD_W)] for _ in range(BOARD_H)]

    PIECES = {
        "I": ([(0, 0), (-1, 0), (1, 0), (2, 0)], C_CYAN),
        "O": ([(0, 0), (1, 0), (0, 1), (1, 1)], C_YELLOW),
        "T": ([(0, 0), (-1, 0), (1, 0), (0, 1)], C_MAGENTA),
        "S": ([(0, 0), (1, 0), (0, 1), (-1, 1)], C_GREEN),
        "Z": ([(0, 0), (-1, 0), (0, 1), (1, 1)], C_RED),
        "J": ([(0, 0), (-1, 0), (1, 0), (-1, 1)], C_BLUE),
        "L": ([(0, 0), (-1, 0), (1, 0), (1, 1)], C_WHITE),
    }

    def can_place(px, py, offsets):
        for ox, oy in offsets:
            x, y = px + ox, py + oy
            if x < 0 or x >= BOARD_W or y < 0 or y >= BOARD_H:
                return False
            if board[y][x] is not None:
                return False
        return True

    def rotate(offsets, ptype):
        if ptype == "O":
            return offsets
        return [(-oy, ox) for ox, oy in offsets]

    piece_keys = list(PIECES.keys())
    cur_type = random.choice(piece_keys)
    cur_offsets, cur_col = PIECES[cur_type]
    next_type = random.choice(piece_keys)
    px, py = BOARD_W // 2, 1
    score = 0
    lines_cleared = 0
    high_score = load_scores().get("tetris", 0)
    fall_speed = 0.45
    last_fall = time.time()

    hide_cursor()
    clear_screen()

    while True:
        now = time.time()
        k = get_key()
        if k in ("q", "escape"):
            return
        elif k in ("left", "a"):
            if can_place(px - 1, py, cur_offsets):
                px -= 1
        elif k in ("right", "d"):
            if can_place(px + 1, py, cur_offsets):
                px += 1
        elif k in ("up", "w"):
            rot = rotate(cur_offsets, cur_type)
            # Wall kicks
            for kx in (0, -1, 1, -2, 2):
                if can_place(px + kx, py, rot):
                    cur_offsets = rot
                    px += kx
                    break
        elif k in ("down", "s"):
            if can_place(px, py + 1, cur_offsets):
                py += 1
                score += 1
        elif k in (" ", "enter"):
            # Hard drop
            drop_dist = 0
            while can_place(px, py + 1, cur_offsets):
                py += 1
                drop_dist += 1
            score += drop_dist * 2
            now = 0  # Force immediate lock

        # Gravity tick
        if now - last_fall > fall_speed or now == 0:
            last_fall = time.time()
            if can_place(px, py + 1, cur_offsets):
                py += 1
            else:
                # Lock piece
                for ox, oy in cur_offsets:
                    board[py + oy][px + ox] = cur_col
                # Check line clears
                cleared = 0
                new_board = []
                for row in board:
                    if all(cell is not None for cell in row):
                        cleared += 1
                    else:
                        new_board.append(row)
                for _ in range(cleared):
                    new_board.insert(0, [None for _ in range(BOARD_W)])
                board = new_board

                if cleared:
                    lines_cleared += cleared
                    score += {1: 100, 2: 300, 3: 500, 4: 800}.get(cleared, 1000)
                    fall_speed = max(0.08, 0.45 - (lines_cleared // 5) * 0.04)

                # Spawn next piece
                cur_type = next_type
                cur_offsets, cur_col = PIECES[cur_type]
                next_type = random.choice(piece_keys)
                px, py = BOARD_W // 2, 1
                if not can_place(px, py, cur_offsets):
                    break

        # Calculate ghost piece
        gy = py
        while can_place(px, gy + 1, cur_offsets):
            gy += 1

        # Render field (each cell = 2 chars wide)
        lines = [
            f"\033[H{C_CYAN}╔═[ 🧩 TETRIS 8-BIT ]════════════════════════════════╗{C_RESET}",
            f"  {C_YELLOW}Score: {score:05d}{C_RESET}   {C_MAGENTA}High: {max(high_score, score):05d}{C_RESET}   {C_GREEN}Lines: {lines_cleared}{C_RESET}   Level: {lines_cleared // 5 + 1}",
            f"  {C_CYAN}╔════════════════════╗{C_RESET}   {C_WHITE}{C_BOLD}NEXT:{C_RESET}",
        ]

        next_off, next_col = PIECES[next_type]
        for y in range(BOARD_H):
            row_str = ""
            for x in range(BOARD_W):
                # Active piece
                is_cur = any((px + ox == x and py + oy == y) for ox, oy in cur_offsets)
                is_ghost = any((px + ox == x and gy + oy == y) for ox, oy in cur_offsets)
                if is_cur:
                    row_str += f"{cur_col}██{C_RESET}"
                elif is_ghost:
                    row_str += f"{C_GRAY}░░{C_RESET}"
                elif board[y][x] is not None:
                    row_str += f"{board[y][x]}██{C_RESET}"
                else:
                    row_str += "  "

            side_panel = ""
            if y == 1:
                # Top of next preview
                prow = ""
                for nx in range(-1, 3):
                    prow += f"{next_col}██{C_RESET}" if any((nx == ox and 0 == oy) for ox, oy in next_off) else "  "
                side_panel = f"   {prow}"
            elif y == 2:
                # Bottom of next preview
                prow = ""
                for nx in range(-1, 3):
                    prow += f"{next_col}██{C_RESET}" if any((nx == ox and 1 == oy) for ox, oy in next_off) else "  "
                side_panel = f"   {prow}"
            elif y == 5:
                side_panel = f"   {C_GRAY}WASD/Arrows: Move{C_RESET}"
            elif y == 6:
                side_panel = f"   {C_GRAY}W/Up: Rotate{C_RESET}"
            elif y == 7:
                side_panel = f"   {C_GRAY}Space: Hard Drop{C_RESET}"
            elif y == 8:
                side_panel = f"   {C_GRAY}Q: Quit{C_RESET}"

            lines.append(f"  {C_CYAN}║{C_RESET}{row_str}{C_CYAN}║{C_RESET}{side_panel}")

        lines.append(f"  {C_CYAN}╚════════════════════╝{C_RESET}")
        sys.stdout.write("\n".join(lines) + "\n")
        sys.stdout.flush()
        time.sleep(0.03)

    save_score("tetris", score)
    game_over_screen("GAME OVER", score, high_score)


# ==============================================================================
# GAME 6: 🐦 FLAPPY BIRD
# ==============================================================================
def play_flappy():
    WIDTH, HEIGHT = 46, 18
    by = 9.0
    vy = 0.0
    gravity = 0.22
    jump = -1.1
    score = 0
    high_score = load_scores().get("flappy", 0)
    pipes = []
    spawn_timer = 0

    hide_cursor()
    clear_screen()

    while True:
        k = get_key()
        if k in ("q", "escape"):
            return
        elif k in (" ", "up", "w", "enter"):
            vy = jump

        vy += gravity
        by += vy

        # Pipe spawner
        spawn_timer += 1
        if spawn_timer >= 18:
            spawn_timer = 0
            gap_y = random.randint(3, HEIGHT - 8)
            pipes.append({"x": WIDTH - 2, "gap_y": gap_y, "scored": False})

        # Move pipes
        new_pipes = []
        for p in pipes:
            p["x"] -= 1.0
            # Check score
            if p["x"] < 8 and not p["scored"]:
                score += 1
                p["scored"] = True
            if p["x"] > 0:
                new_pipes.append(p)
        pipes = new_pipes

        # Check collisions
        if by <= 1 or by >= HEIGHT - 2:
            break
        collision = False
        for p in pipes:
            if abs(p["x"] - 8) < 1.8:
                if by < p["gap_y"] or by >= p["gap_y"] + 5:
                    collision = True
                    break
        if collision:
            break

        # Render frame
        grid = [[" " for _ in range(WIDTH)] for _ in range(HEIGHT)]
        for x in range(WIDTH):
            grid[0][x] = "═"
            grid[HEIGHT - 1][x] = f"{C_GREEN}█{C_RESET}"

        # Draw pipes
        for p in pipes:
            px = int(p["x"])
            if 0 < px < WIDTH - 1:
                for y in range(1, HEIGHT - 1):
                    if y < p["gap_y"] or y >= p["gap_y"] + 5:
                        grid[y][px] = f"{C_GREEN}█{C_RESET}"

        # Draw bird
        iby = max(1, min(HEIGHT - 2, int(by)))
        bird_sprite = f"{C_YELLOW}{C_BOLD}►{C_RESET}" if vy >= 0 else f"{C_YELLOW}{C_BOLD}▲{C_RESET}"
        grid[iby][8] = bird_sprite

        frame = [
            f"\033[H{C_CYAN}╔═[ 🐦 FLAPPY BIRD 8-BIT ]═══════════════════════════╗{C_RESET}",
            f"  {C_YELLOW}Score: {score:03d}{C_RESET}   {C_MAGENTA}High: {max(high_score, score):03d}{C_RESET}   {C_GRAY}(Space / W to flap · Q to quit){C_RESET}",
        ]
        for row in grid:
            frame.append("  " + "".join(row))
        sys.stdout.write("\n".join(frame) + "\n")
        sys.stdout.flush()
        time.sleep(0.045)

    save_score("flappy", score)
    game_over_screen("FLAP OVER", score, high_score)


# ==============================================================================
# GAME 7: 🟡 PAC-MAZE
# ==============================================================================
def play_pacmaze():
    RAW_MAZE = [
        "████████████████████████████",
        "█············██············█",
        "█·████·█████·██·█████·████·█",
        "█●████·█████·██·█████·████●█",
        "█··························█",
        "█·████·██·████████·██·████·█",
        "█······██····██····██······█",
        "██████·█████ ██ █████·██████",
        "      ·██          ██·      ",
        "██████·██ ████████ ██·██████",
        "█············██············█",
        "█·████·█████·██·█████·████·█",
        "█●··██·······  ·······██··●█",
        "███·██·██·████████·██·██·███",
        "████████████████████████████",
    ]
    H, W = len(RAW_MAZE), len(RAW_MAZE[0])
    maze = [list(row) for row in RAW_MAZE]
    px, py = 14, 10
    score = 0
    high_score = load_scores().get("pacmaze", 0)
    lives = 3
    scared_timer = 0

    ghosts = [
        {"x": 13, "y": 8, "color": C_RED, "char": "M"},
        {"x": 14, "y": 8, "color": C_MAGENTA, "char": "W"},
    ]

    hide_cursor()
    clear_screen()

    tick = 0
    while lives > 0:
        tick += 1
        k = get_key()
        if k in ("q", "escape"):
            return
        dx, dy = 0, 0
        if k in ("up", "w"):
            dy = -1
        elif k in ("down", "s"):
            dy = 1
        elif k in ("left", "a"):
            dx = -1
        elif k in ("right", "d"):
            dx = 1

        nx, ny = px + dx, py + dy
        # Wrap tunnels
        if nx < 0:
            nx = W - 1
        elif nx >= W:
            nx = 0

        if maze[ny][nx] != "█":
            px, py = nx, ny
            cell = maze[py][px]
            if cell == "·":
                score += 10
                maze[py][px] = " "
            elif cell == "●":
                score += 50
                maze[py][px] = " "
                scared_timer = 35

        if scared_timer > 0:
            scared_timer -= 1

        # Move ghosts every 2 ticks
        if tick % 2 == 0:
            for g in ghosts:
                dirs = [(0, -1), (0, 1), (-1, 0), (1, 0)]
                valid = []
                for gx, gy in dirs:
                    gx_next, gy_next = g["x"] + gx, g["y"] + gy
                    if 0 <= gy_next < H and 0 <= gx_next < W and maze[gy_next][gx_next] != "█":
                        valid.append((gx_next, gy_next))
                if valid:
                    if scared_timer > 0:
                        # Move randomly away from Pac-Man
                        g["x"], g["y"] = max(valid, key=lambda p: abs(p[0] - px) + abs(p[1] - py))
                    else:
                        # Chase Pac-Man
                        g["x"], g["y"] = min(valid, key=lambda p: abs(p[0] - px) + abs(p[1] - py))

        # Check ghost collisions
        for g in ghosts:
            if g["x"] == px and g["y"] == py:
                if scared_timer > 0:
                    score += 200
                    g["x"], g["y"] = 13, 8
                else:
                    lives -= 1
                    px, py = 14, 10
                    time.sleep(0.4)
                    break

        # Check win
        pellets_left = sum(row.count("·") + row.count("●") for row in maze)
        if pellets_left == 0:
            score += 1000
            break

        # Render maze
        render_grid = [list(r) for r in maze]
        for r in range(H):
            for c in range(W):
                ch = render_grid[r][c]
                if ch == "█":
                    render_grid[r][c] = f"{C_BLUE}█{C_RESET}"
                elif ch == "·":
                    render_grid[r][c] = f"{C_YELLOW}·{C_RESET}"
                elif ch == "●":
                    render_grid[r][c] = f"{C_WHITE}{C_BOLD}●{C_RESET}"

        # Draw ghosts
        for g in ghosts:
            if scared_timer > 0:
                render_grid[g["y"]][g["x"]] = f"{C_CYAN}~{C_RESET}"
            else:
                render_grid[g["y"]][g["x"]] = f"{g['color']}{g['char']}{C_RESET}"

        # Draw Pac-Man
        render_grid[py][px] = f"{C_YELLOW}{C_BOLD}C{C_RESET}"

        hearts = f"{C_RED}{'❤ ' * lives}{C_RESET}"
        status = f"{C_CYAN}GHOSTS SCARED!{C_RESET}" if scared_timer > 0 else f"{C_GRAY}WASD/Arrows to eat{C_RESET}"
        frame = [
            f"\033[H{C_CYAN}╔═[ 🟡 PAC-MAZE 8-BIT ]═══════════════════════╗{C_RESET}",
            f"  {C_YELLOW}Score: {score:05d}{C_RESET}   {C_MAGENTA}High: {max(high_score, score):05d}{C_RESET}   Lives: {hearts}  {status}",
        ]
        for row in render_grid:
            frame.append("  " + "".join(row))
        sys.stdout.write("\n".join(frame) + "\n")
        sys.stdout.flush()
        time.sleep(0.065)

    save_score("pacmaze", score)
    msg = f"{C_GREEN}MAZE CLEARED! 🏆{C_RESET}" if lives > 0 else f"{C_RED}CAUGHT!{C_RESET}"
    game_over_screen(msg, score, high_score)


# ==============================================================================
# GAME 8: 🐸 FROGGER
# ==============================================================================
def play_frogger():
    WIDTH, HEIGHT = 44, 13
    frog_x, frog_y = WIDTH // 2, 11
    score = 0
    lives = 3
    high_score = load_scores().get("frogger", 0)
    goals = [False] * 5
    goal_xs = [4, 12, 20, 28, 36]

    # Lanes: y -> [{"x": float, "w": int, "speed": float, "type": "car"|"log"}]
    lanes = {
        2: {"speed": 0.45, "objs": [0, 16, 32], "w": 6, "type": "log"},
        3: {"speed": -0.55, "objs": [4, 20, 36], "w": 5, "type": "log"},
        4: {"speed": 0.40, "objs": [2, 18, 34], "w": 7, "type": "log"},
        6: {"speed": -0.6, "objs": [6, 22, 38], "w": 4, "type": "car"},
        7: {"speed": 0.7, "objs": [2, 18, 34], "w": 3, "type": "car"},
        8: {"speed": -0.5, "objs": [8, 24, 40], "w": 4, "type": "car"},
    }

    hide_cursor()
    clear_screen()

    while lives > 0 and not all(goals):
        k = get_key()
        if k in ("q", "escape"):
            return
        elif k in ("up", "w") and frog_y > 1:
            frog_y -= 1
            score += 10
        elif k in ("down", "s") and frog_y < 11:
            frog_y += 1
        elif k in ("left", "a") and frog_x > 2:
            frog_x -= 2
        elif k in ("right", "d") and frog_x < WIDTH - 3:
            frog_x += 2

        # Update lanes
        for ly, ldata in lanes.items():
            for i in range(len(ldata["objs"])):
                ldata["objs"][i] = (ldata["objs"][i] + ldata["speed"]) % WIDTH

        # Check hazards
        dead = False
        if 6 <= frog_y <= 8:  # Highway
            for ox in lanes[frog_y]["objs"]:
                if ox <= frog_x < ox + lanes[frog_y]["w"]:
                    dead = True
                    break
        elif 2 <= frog_y <= 4:  # River
            on_log = False
            for ox in lanes[frog_y]["objs"]:
                if ox <= frog_x < ox + lanes[frog_y]["w"]:
                    on_log = True
                    frog_x += lanes[frog_y]["speed"]
                    break
            if not on_log or frog_x <= 0 or frog_x >= WIDTH - 1:
                dead = True
        elif frog_y == 1:  # Lily pads
            hit_goal = False
            for idx, gx in enumerate(goal_xs):
                if abs(frog_x - gx) <= 2:
                    if not goals[idx]:
                        goals[idx] = True
                        score += 200
                        hit_goal = True
                    break
            if hit_goal:
                frog_x, frog_y = WIDTH // 2, 11
            else:
                dead = True

        if dead:
            lives -= 1
            frog_x, frog_y = WIDTH // 2, 11
            time.sleep(0.4)
            continue

        # Render field
        grid = [[" " for _ in range(WIDTH)] for _ in range(HEIGHT)]
        # Borders
        for x in range(WIDTH):
            grid[0][x] = "═"
            grid[HEIGHT - 1][x] = "═"

        # Goal row
        for x in range(WIDTH):
            grid[1][x] = f"{C_BLUE}≈{C_RESET}"
        for idx, gx in enumerate(goal_xs):
            icon = f"{C_GREEN}✿{C_RESET}" if goals[idx] else f"{C_YELLOW}○{C_RESET}"
            grid[1][gx] = icon

        # River lanes
        for ly in range(2, 5):
            for x in range(WIDTH):
                grid[ly][x] = f"{C_BLUE}≈{C_RESET}"
            for ox in lanes[ly]["objs"]:
                for w in range(lanes[ly]["w"]):
                    pos = int(ox + w) % WIDTH
                    grid[ly][pos] = f"{C_YELLOW}═{C_RESET}"

        # Median sidewalk
        for x in range(WIDTH):
            grid[5][x] = f"{C_GRAY}░{C_RESET}"
            grid[9][x] = f"{C_GRAY}░{C_RESET}"
            grid[10][x] = f"{C_GRAY}░{C_RESET}"
            grid[11][x] = f"{C_GRAY}░{C_RESET}"

        # Highway lanes
        for ly in range(6, 9):
            for ox in lanes[ly]["objs"]:
                for w in range(lanes[ly]["w"]):
                    pos = int(ox + w) % WIDTH
                    grid[ly][pos] = f"{C_RED}█{C_RESET}"

        # Frog
        ifx = max(1, min(WIDTH - 2, int(frog_x)))
        ify = max(1, min(HEIGHT - 2, int(frog_y)))
        grid[ify][ifx] = f"{C_GREEN}{C_BOLD}🐸{C_RESET}"

        hearts = f"{C_RED}{'❤ ' * lives}{C_RESET}"
        frame = [
            f"\033[H{C_CYAN}╔═[ 🐸 FROGGER 8-BIT ]═══════════════════════════════╗{C_RESET}",
            f"  {C_YELLOW}Score: {score:04d}{C_RESET}   {C_MAGENTA}High: {max(high_score, score):04d}{C_RESET}   Lives: {hearts}  {C_GRAY}(WASD / Arrows to hop){C_RESET}",
        ]
        for row in grid:
            frame.append("  " + "".join(row))
        sys.stdout.write("\n".join(frame) + "\n")
        sys.stdout.flush()
        time.sleep(0.05)

    if all(goals):
        score += 1000
    save_score("frogger", score)
    msg = f"{C_GREEN}ALL FROGS HOME! 🏆{C_RESET}" if all(goals) else f"{C_RED}GAME OVER!{C_RESET}"
    game_over_screen(msg, score, high_score)


# ==============================================================================
# GAME 9: ☄️ ASTEROIDS
# ==============================================================================
def play_asteroids():
    WIDTH, HEIGHT = 50, 20
    px, py = WIDTH / 2, HEIGHT / 2
    vx, vy = 0.0, 0.0
    angle = 0  # 0..7 (0: N, 1: NE, 2: E, 3: SE, 4: S, 5: SW, 6: W, 7: NW)
    DIR_VECS = [(0, -1), (0.9, -0.7), (1.3, 0), (0.9, 0.7), (0, 1), (-0.9, 0.7), (-1.3, 0), (-0.9, -0.7)]
    SHIP_SPRITES = ["▲", "↗", "►", "↘", "▼", "↙", "◄", "↖"]

    bullets = []
    score = 0
    lives = 3
    high_score = load_scores().get("asteroids", 0)

    # Asteroids: [{"x", "y", "vx", "vy", "size": 3|2|1}]
    asteroids = []
    for _ in range(4):
        asteroids.append({
            "x": random.choice([5.0, 45.0]),
            "y": random.choice([3.0, 17.0]),
            "vx": random.uniform(-0.5, 0.5),
            "vy": random.uniform(-0.4, 0.4),
            "size": 3,
        })

    hide_cursor()
    clear_screen()

    while lives > 0 and asteroids:
        k = get_key()
        if k in ("q", "escape"):
            return
        elif k in ("left", "a"):
            angle = (angle - 1) % 8
        elif k in ("right", "d"):
            angle = (angle + 1) % 8
        elif k in ("up", "w"):
            vx += DIR_VECS[angle][0] * 0.25
            vy += DIR_VECS[angle][1] * 0.18
        elif k in (" ", "enter"):
            if len(bullets) < 4:
                bullets.append({"x": px, "y": py, "vx": DIR_VECS[angle][0] * 1.5, "vy": DIR_VECS[angle][1] * 1.2, "life": 16})

        # Inertia and wrap-around
        vx *= 0.96
        vy *= 0.96
        px = (px + vx) % WIDTH
        py = (py + vy) % HEIGHT

        # Update bullets
        new_bullets = []
        for b in bullets:
            b["x"] = (b["x"] + b["vx"]) % WIDTH
            b["y"] = (b["y"] + b["vy"]) % HEIGHT
            b["life"] -= 1
            if b["life"] > 0:
                new_bullets.append(b)
        bullets = new_bullets

        # Update asteroids
        for a in asteroids:
            a["x"] = (a["x"] + a["vx"]) % WIDTH
            a["y"] = (a["y"] + a["vy"]) % HEIGHT

        # Bullet - Asteroid collision
        new_asteroids = []
        for a in list(asteroids):
            hit = False
            for b in list(bullets):
                dist = math.hypot(a["x"] - b["x"], (a["y"] - b["y"]) * 1.4)
                if dist < a["size"]:
                    hit = True
                    bullets.remove(b)
                    score += {3: 20, 2: 50, 1: 100}[a["size"]]
                    if a["size"] > 1:
                        for _ in range(2):
                            new_asteroids.append({
                                "x": a["x"], "y": a["y"],
                                "vx": random.uniform(-0.6, 0.6), "vy": random.uniform(-0.5, 0.5),
                                "size": a["size"] - 1
                            })
                    break
            if not hit:
                new_asteroids.append(a)
        asteroids = new_asteroids

        # Ship - Asteroid collision
        for a in asteroids:
            dist = math.hypot(a["x"] - px, (a["y"] - py) * 1.4)
            if dist < a["size"] + 0.8:
                lives -= 1
                px, py = WIDTH / 2, HEIGHT / 2
                vx, vy = 0.0, 0.0
                time.sleep(0.4)
                break

        # Render field
        grid = [[" " for _ in range(WIDTH)] for _ in range(HEIGHT)]
        for x in range(WIDTH):
            grid[0][x] = "═"
            grid[HEIGHT - 1][x] = "═"
        for y in range(HEIGHT):
            grid[y][0] = "║"
            grid[y][WIDTH - 1] = "║"

        # Draw asteroids
        for a in asteroids:
            ax, ay = int(a["x"]), int(a["y"])
            if 0 < ay < HEIGHT - 1 and 0 < ax < WIDTH - 1:
                sprite = f"{C_GRAY}(●){C_RESET}" if a["size"] == 3 else (f"{C_YELLOW}(o){C_RESET}" if a["size"] == 2 else f"{C_WHITE}·{C_RESET}")
                grid[ay][ax] = sprite

        # Draw bullets
        for b in bullets:
            bx, by = int(b["x"]), int(b["y"])
            if 0 < by < HEIGHT - 1 and 0 < bx < WIDTH - 1:
                grid[by][bx] = f"{C_YELLOW}*{C_RESET}"

        # Draw ship
        ipx, ipy = int(px), int(py)
        if 0 < ipy < HEIGHT - 1 and 0 < ipx < WIDTH - 1:
            grid[ipy][ipx] = f"{C_CYAN}{C_BOLD}{SHIP_SPRITES[angle]}{C_RESET}"

        hearts = f"{C_RED}{'❤ ' * lives}{C_RESET}"
        frame = [
            f"\033[H{C_CYAN}╔═[ ☄️ ASTEROIDS 8-BIT ]═════════════════════════════╗{C_RESET}",
            f"  {C_YELLOW}Score: {score:04d}{C_RESET}   {C_MAGENTA}High: {max(high_score, score):04d}{C_RESET}   Lives: {hearts}  {C_GRAY}(A/D: Turn · W: Thrust · Space: Fire){C_RESET}",
        ]
        for row in grid:
            frame.append("  " + "".join(row))
        sys.stdout.write("\n".join(frame) + "\n")
        sys.stdout.flush()
        time.sleep(0.04)

    save_score("asteroids", score)
    msg = f"{C_GREEN}SECTOR CLEARED! 🏆{C_RESET}" if not asteroids else f"{C_RED}SHIP DESTROYED!{C_RESET}"
    game_over_screen(msg, score, high_score)


# ==============================================================================
# GAME 10: 🗡️ MINI-ROGUE (ASCII DUNGEON CRAWLER)
# ==============================================================================
def play_minirogue():
    WIDTH, HEIGHT = 48, 16
    score = 0
    high_score = load_scores().get("minirogue", 0)
    floor = 1
    player_hp = 20
    player_max_hp = 20
    player_atk = 4
    player_def = 1
    msg_log = "Welcome to the dungeon! WASD to explore."

    hide_cursor()
    clear_screen()

    while player_hp > 0:
        # Generate procedural rooms
        dungeon = [["█" for _ in range(WIDTH)] for _ in range(HEIGHT)]
        rooms = []
        for _ in range(4):
            rw = random.randint(6, 12)
            rh = random.randint(4, 7)
            rx = random.randint(2, WIDTH - rw - 3)
            ry = random.randint(2, HEIGHT - rh - 3)
            # Carve room
            for y in range(ry, ry + rh):
                for x in range(rx, rx + rw):
                    dungeon[y][x] = "."
            rooms.append((rx + rw // 2, ry + rh // 2))

        # Connect rooms with corridors
        for i in range(len(rooms) - 1):
            x1, y1 = rooms[i]
            x2, y2 = rooms[i + 1]
            for x in range(min(x1, x2), max(x1, x2) + 1):
                dungeon[y1][x] = "."
            for y in range(min(y1, y2), max(y1, y2) + 1):
                dungeon[y][x2] = "."

        px, py = rooms[0]
        stairs_x, stairs_y = rooms[-1]
        dungeon[stairs_y][stairs_x] = ">"

        # Spawn monsters and items
        monsters = []
        items = []
        for rx, ry in rooms[1:]:
            m_type = random.choice([("g", 6, 2, "Goblin"), ("s", 10, 3, "Skeleton"), ("O", 15, 4, "Orc")])
            monsters.append({"x": rx, "y": ry, "char": m_type[0], "hp": m_type[1], "atk": m_type[2], "name": m_type[3]})
            i_type = random.choice([("$", "Gold"), ("!", "Potion"), ("/", "Sword"), ("[", "Shield")])
            items.append({"x": rx + 1, "y": ry, "char": i_type[0], "type": i_type[1]})

        floor_cleared = False
        while player_hp > 0 and not floor_cleared:
            # Render
            grid = [list(r) for r in dungeon]
            for it in items:
                grid[it["y"]][it["x"]] = f"{C_YELLOW}{it['char']}{C_RESET}"
            for m in monsters:
                grid[m["y"]][m["x"]] = f"{C_RED}{m['char']}{C_RESET}"
            grid[stairs_y][stairs_x] = f"{C_MAGENTA}>{C_RESET}"
            grid[py][px] = f"{C_GREEN}{C_BOLD}@{C_RESET}"

            hp_bar = f"{C_GREEN}{player_hp}/{player_max_hp}{C_RESET}"
            frame = [
                f"\033[H{C_CYAN}╔═[ 🗡️ MINI-ROGUE DUNGEON ]═══════════════════════════╗{C_RESET}",
                f"  Floor: {floor}   HP: {hp_bar}   ATK: {player_atk}   DEF: {player_def}   Score: {score}",
            ]
            for row in grid:
                frame.append("  " + "".join(row))
            frame.append(f"  {C_YELLOW}Log: {msg_log}{C_RESET}")
            sys.stdout.write("\n".join(frame) + "\n")
            sys.stdout.flush()

            # Wait for turn input
            while True:
                k = get_key()
                if k in ("q", "escape"):
                    return
                elif k in ("up", "w"):
                    dx, dy = 0, -1
                    break
                elif k in ("down", "s"):
                    dx, dy = 0, 1
                    break
                elif k in ("left", "a"):
                    dx, dy = -1, 0
                    break
                elif k in ("right", "d"):
                    dx, dy = 1, 0
                    break
                time.sleep(0.04)

            nx, ny = px + dx, py + dy
            # Attack monster
            attacked = False
            for m in list(monsters):
                if m["x"] == nx and m["y"] == ny:
                    dmg = max(1, player_atk + random.randint(-1, 1))
                    m["hp"] -= dmg
                    msg_log = f"You hit {m['name']} for {dmg} damage!"
                    if m["hp"] <= 0:
                        monsters.remove(m)
                        score += 50
                        msg_log += f" Slain {m['name']}!"
                    attacked = True
                    break

            if not attacked and dungeon[ny][nx] != "█":
                px, py = nx, ny
                # Pick up items
                for it in list(items):
                    if it["x"] == px and it["y"] == py:
                        if it["type"] == "Gold":
                            score += 40
                            msg_log = "Found a pile of gold! (+40 pts)"
                        elif it["type"] == "Potion":
                            player_hp = min(player_max_hp, player_hp + 8)
                            msg_log = "Drank potion! (+8 HP)"
                        elif it["type"] == "Sword":
                            player_atk += 2
                            msg_log = "Found a sharp sword! (+2 ATK)"
                        elif it["type"] == "Shield":
                            player_def += 1
                            msg_log = "Equipped a sturdy shield! (+1 DEF)"
                        items.remove(it)

                # Stairs
                if px == stairs_x and py == stairs_y:
                    floor += 1
                    score += 200
                    floor_cleared = True
                    msg_log = f"Descended deeper into floor {floor}!"
                    break

            # Monsters turn
            for m in monsters:
                if math.hypot(m["x"] - px, m["y"] - py) < 6:
                    # Adjacent -> attack player
                    if abs(m["x"] - px) + abs(m["y"] - py) == 1:
                        mdmg = max(1, m["atk"] - player_def)
                        player_hp -= mdmg
                        msg_log = f"{m['name']} strikes you for {mdmg} damage!"
                    else:
                        # Move toward player
                        step_x = 1 if px > m["x"] else (-1 if px < m["x"] else 0)
                        step_y = 1 if py > m["y"] else (-1 if py < m["y"] else 0)
                        if dungeon[m["y"] + step_y][m["x"]] != "█":
                            m["y"] += step_y
                        elif dungeon[m["y"]][m["x"] + step_x] != "█":
                            m["x"] += step_x

    save_score("minirogue", score)
    game_over_screen("HERO HAS FALLEN", score, high_score)


# ==============================================================================
# GAME 11: 🔢 2048
# ==============================================================================
def play_2048():
    board = [[0] * 4 for _ in range(4)]
    score = 0
    high_score = load_scores().get("2048", 0)

    def spawn_tile():
        empty = [(r, c) for r in range(4) for c in range(4) if board[r][c] == 0]
        if empty:
            r, c = random.choice(empty)
            board[r][c] = 4 if random.random() < 0.1 else 2

    spawn_tile()
    spawn_tile()

    hide_cursor()
    clear_screen()

    def slide_left(b):
        new_b = []
        added = 0
        for row in b:
            nums = [x for x in row if x != 0]
            merged = []
            i = 0
            while i < len(nums):
                if i + 1 < len(nums) and nums[i] == nums[i + 1]:
                    val = nums[i] * 2
                    merged.append(val)
                    added += val
                    i += 2
                else:
                    merged.append(nums[i])
                    i += 1
            merged.extend([0] * (4 - len(merged)))
            new_b.append(merged)
        return new_b, added

    def rotate_cw(b):
        return [list(row) for row in zip(*b[::-1])]

    TILE_COLORS = {
        2: C_WHITE,
        4: C_YELLOW,
        8: C_RED,
        16: f"{C_BOLD}{C_RED}",
        32: C_MAGENTA,
        64: f"{C_BOLD}{C_MAGENTA}",
        128: C_CYAN,
        256: f"{C_BOLD}{C_CYAN}",
        512: C_GREEN,
        1024: f"{C_BOLD}{C_GREEN}",
        2048: f"{C_YELLOW}{C_BOLD}",
    }

    while True:
        # Render board
        lines = [
            f"\033[H{C_CYAN}╔═[ 🔢 2048 PUZZLE ]═════════════════════════════════╗{C_RESET}",
            f"  {C_YELLOW}Score: {score:06d}{C_RESET}   {C_MAGENTA}High: {max(high_score, score):06d}{C_RESET}   {C_GRAY}(WASD / Arrows to slide){C_RESET}",
            f"  {C_CYAN}┌──────┬──────┬──────┬──────┐{C_RESET}",
        ]
        for r in range(4):
            row_str = "  │"
            for c in range(4):
                val = board[r][c]
                if val == 0:
                    row_str += "      │"
                else:
                    color = TILE_COLORS.get(val, C_WHITE)
                    row_str += f"{color}{val:^6}{C_RESET}│"
            lines.append(row_str)
            if r < 3:
                lines.append(f"  {C_CYAN}├──────┼──────┼──────┼──────┤{C_RESET}")
        lines.append(f"  {C_CYAN}└──────┴──────┴──────┴──────┘{C_RESET}")
        lines.append(f"  {C_GRAY}Join numbers to reach the 2048 tile! · Q to quit{C_RESET}")
        sys.stdout.write("\n".join(lines) + "\n")
        sys.stdout.flush()

        k = get_key()
        if not k:
            time.sleep(0.04)
            continue

        if k in ("q", "escape"):
            return

        moved = False
        add_pts = 0
        if k in ("left", "a"):
            new_b, add_pts = slide_left(board)
            if new_b != board:
                board = new_b
                moved = True
        elif k in ("right", "d"):
            b1 = rotate_cw(rotate_cw(board))
            b2, add_pts = slide_left(b1)
            new_b = rotate_cw(rotate_cw(b2))
            if new_b != board:
                board = new_b
                moved = True
        elif k in ("up", "w"):
            b1 = rotate_cw(rotate_cw(rotate_cw(board)))
            b2, add_pts = slide_left(b1)
            new_b = rotate_cw(b2)
            if new_b != board:
                board = new_b
                moved = True
        elif k in ("down", "s"):
            b1 = rotate_cw(board)
            b2, add_pts = slide_left(b1)
            new_b = rotate_cw(rotate_cw(rotate_cw(b2)))
            if new_b != board:
                board = new_b
                moved = True

        if moved:
            score += add_pts
            spawn_tile()

            # Check game over
            has_empty = any(0 in row for row in board)
            can_merge = False
            for r in range(4):
                for c in range(4):
                    if r < 3 and board[r][c] == board[r + 1][c]:
                        can_merge = True
                    if c < 3 and board[r][c] == board[r][c + 1]:
                        can_merge = True
            if not has_empty and not can_merge:
                break

    save_score("2048", score)
    game_over_screen("NO MORE MOVES", score, high_score)


# ==============================================================================
# GAME 12: 💣 MINESWEEPER
# ==============================================================================
def play_minesweeper():
    COLS, ROWS = 12, 10
    MINES = 15
    cx, cy = COLS // 2, ROWS // 2
    mines = set()
    revealed = set()
    flagged = set()
    first_click = True
    high_score = load_scores().get("minesweeper", 0)
    score = 0
    start_time = None

    hide_cursor()
    clear_screen()

    def get_adjacent_count(x, y):
        return sum(1 for dx in (-1, 0, 1) for dy in (-1, 0, 1) if (x + dx, y + dy) in mines)

    def reveal(x, y):
        if (x, y) in flagged or (x, y) in revealed or not (0 <= x < COLS and 0 <= y < ROWS):
            return
        revealed.add((x, y))
        if get_adjacent_count(x, y) == 0:
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    reveal(x + dx, y + dy)

    NUM_COLORS = {
        1: C_BLUE, 2: C_GREEN, 3: C_RED, 4: C_MAGENTA,
        5: C_YELLOW, 6: C_CYAN, 7: C_WHITE, 8: C_GRAY
    }

    game_won = False
    game_lost = False

    while not game_won and not game_lost:
        # Render board
        elapsed = int(time.time() - start_time) if start_time else 0
        lines = [
            f"\033[H{C_CYAN}╔═[ 💣 MINESWEEPER 8-BIT ]═══════════════════════════╗{C_RESET}",
            f"  {C_RED}Mines: {MINES - len(flagged):02d}{C_RESET}   {C_YELLOW}Time: {elapsed:03d}s{C_RESET}   {C_MAGENTA}Best: {high_score:04d}{C_RESET}   {C_GRAY}(Space: Reveal · F: Flag){C_RESET}",
            f"  {C_CYAN}┌" + "──" * COLS + f"┐{C_RESET}",
        ]

        for y in range(ROWS):
            row_str = "  │"
            for x in range(COLS):
                is_cur = (x == cx and y == cy)
                bracket_l = f"{C_YELLOW}[{C_RESET}" if is_cur else " "
                bracket_r = f"{C_YELLOW}]{C_RESET}" if is_cur else " "

                if (x, y) in flagged:
                    cell_ch = f"{C_RED}⚑{C_RESET}"
                elif (x, y) in revealed:
                    if (x, y) in mines:
                        cell_ch = f"{C_RED}✹{C_RESET}"
                    else:
                        cnt = get_adjacent_count(x, y)
                        cell_ch = f"{NUM_COLORS[cnt]}{cnt}{C_RESET}" if cnt > 0 else " "
                else:
                    cell_ch = f"{C_GRAY}·{C_RESET}"
                row_str += cell_ch + (" " if not is_cur else f"{C_YELLOW}◄{C_RESET}")
            lines.append(row_str + "│")
        lines.append(f"  {C_CYAN}└" + "──" * COLS + f"┘{C_RESET}")
        lines.append(f"  {C_GRAY}WASD/Arrows: Move  •  Space/Enter: Open  •  F: Flag  •  Q: Quit{C_RESET}")
        sys.stdout.write("\n".join(lines) + "\n")
        sys.stdout.flush()

        k = get_key()
        if not k:
            time.sleep(0.04)
            continue

        if k in ("q", "escape"):
            return
        elif k in ("up", "w") and cy > 0:
            cy -= 1
        elif k in ("down", "s") and cy < ROWS - 1:
            cy += 1
        elif k in ("left", "a") and cx > 0:
            cx -= 1
        elif k in ("right", "d") and cx < COLS - 1:
            cx += 1
        elif k == "f":
            if (cx, cy) not in revealed:
                if (cx, cy) in flagged:
                    flagged.remove((cx, cy))
                else:
                    flagged.add((cx, cy))
        elif k in (" ", "enter"):
            if first_click:
                first_click = False
                start_time = time.time()
                # Populate mines excluding safe starting cluster
                candidates = [(x, y) for x in range(COLS) for y in range(ROWS) if abs(x - cx) > 1 or abs(y - cy) > 1]
                mines = set(random.sample(candidates, MINES))

            if (cx, cy) not in flagged:
                if (cx, cy) in mines:
                    revealed.update(mines)
                    game_lost = True
                else:
                    reveal(cx, cy)
                    if len(revealed) == COLS * ROWS - MINES:
                        game_won = True
                        score = max(100, 1000 - elapsed * 5)

    save_score("minesweeper", score)
    msg = f"{C_GREEN}MINEFIELD CLEARED! 🏆{C_RESET}" if game_won else f"{C_RED}BOOM! GAME OVER!{C_RESET}"
    game_over_screen(msg, score, high_score)


# ==============================================================================
# MAIN ARCADE MENU (12 GAMES IN 2-COLUMN RETRO CABINET)
# ==============================================================================
def arcade_menu():
    hide_cursor()
    selected_idx = 0

    games = [
        {"num": "1", "name": "🐍 Snake", "key": "snake", "fn": play_snake},
        {"num": "2", "name": "🏓 Pong", "key": "pong", "fn": play_pong},
        {"num": "3", "name": "🚀 Galactica", "key": "galactica", "fn": play_galactica},
        {"num": "4", "name": "🧱 Breakout", "key": "breakout", "fn": play_breakout},
        {"num": "5", "name": "🧩 Tetris", "key": "tetris", "fn": play_tetris},
        {"num": "6", "name": "🐦 Flappy Bird", "key": "flappy", "fn": play_flappy},
        {"num": "7", "name": "🟡 Pac-Maze", "key": "pacmaze", "fn": play_pacmaze},
        {"num": "8", "name": "🐸 Frogger", "key": "frogger", "fn": play_frogger},
        {"num": "9", "name": "☄️ Asteroids", "key": "asteroids", "fn": play_asteroids},
        {"num": "0", "name": "🗡️ Mini-Rogue", "key": "minirogue", "fn": play_minirogue},
        {"num": "-", "name": "🔢 2048", "key": "2048", "fn": play_2048},
        {"num": "=", "name": "💣 Minesweeper", "key": "minesweeper", "fn": play_minesweeper},
    ]

    HOTKEY_MAP = {
        "1": 0, "2": 1, "3": 2, "4": 3, "5": 4, "6": 5,
        "7": 6, "8": 7, "9": 8, "0": 9, "-": 10, "=": 11
    }

    def render():
        clear_screen()
        scores = load_scores()
        lines = [
            f"{C_CYAN}{C_BOLD}",
            r"   █████╗ ██████╗  ██████╗ █████╗ ██████╗ ███████╗",
            r"  ██╔══██╗██╔══██╗██╔════╝██╔══██╗██╔══██╗██╔════╝",
            r"  ███████║██████╔╝██║     ███████║██║  ██║█████╗  ",
            r"  ██╔══██║██╔══██╗██║     ██╔══██║██║  ██║██╔══╝  ",
            r"  ██║  ██║██║  ██║╚██████╗██║  ██║██████╔╝███████╗",
            r"  ╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝╚═╝  ╚═╝╚═════╝ ╚══════╝" + C_RESET,
            f"       {C_YELLOW}★ 8-BIT TERMINAL RETRO ARCADE • 12-IN-1 PACK ★{C_RESET}",
            f"   {C_GRAY}100% Offline • Zero Dependencies • Pure Python & ANSI{C_RESET}",
            f"  {C_CYAN}────────────────────────────────────────────────────────────────{C_RESET}",
        ]

        # Render 6 rows x 2 columns
        for row in range(6):
            # Left column
            idx_l = row
            g_l = games[idx_l]
            is_sel_l = (idx_l == selected_idx)
            ptr_l = f"{C_YELLOW}{C_BOLD}►{C_RESET}" if is_sel_l else " "
            brk_l = f"{C_YELLOW}[{g_l['num']}]{C_RESET}" if is_sel_l else f"{C_CYAN}[{g_l['num']}]{C_RESET}"
            name_l = f"{C_WHITE}{C_BOLD}{g_l['name']:<15}{C_RESET}" if is_sel_l else f"{C_WHITE}{g_l['name']:<15}{C_RESET}"
            best_l = f"{C_YELLOW}{scores.get(g_l['key'], 0):>4}{C_RESET}"
            col_l = f" {ptr_l} {brk_l} {name_l} {C_GRAY}Best:{C_RESET}{best_l}"

            # Right column
            idx_r = row + 6
            g_r = games[idx_r]
            is_sel_r = (idx_r == selected_idx)
            ptr_r = f"{C_YELLOW}{C_BOLD}►{C_RESET}" if is_sel_r else " "
            brk_r = f"{C_YELLOW}[{g_r['num']}]{C_RESET}" if is_sel_r else f"{C_CYAN}[{g_r['num']}]{C_RESET}"
            name_r = f"{C_WHITE}{C_BOLD}{g_r['name']:<15}{C_RESET}" if is_sel_r else f"{C_WHITE}{g_r['name']:<15}{C_RESET}"
            best_r = f"{C_YELLOW}{scores.get(g_r['key'], 0):>4}{C_RESET}"
            col_r = f" {ptr_r} {brk_r} {name_r} {C_GRAY}Best:{C_RESET}{best_r}"

            lines.append(f"{col_l}   │{col_r}")

        lines.append(f"  {C_CYAN}────────────────────────────────────────────────────────────────{C_RESET}")
        lines.append(f"  {C_GRAY}Browse: {C_WHITE}[↑/↓/←/→]{C_GRAY} or {C_WHITE}[WASD]{C_GRAY}  •  Play: {C_WHITE}[Enter/Space]{C_GRAY}  •  Hotkeys: {C_WHITE}[1-9, 0, -, =]{C_GRAY}  •  Exit: {C_WHITE}[Q]{C_RESET}")
        lines.append("")
        cur_name = games[selected_idx]['name']
        lines.append(f"  {C_YELLOW}► Press Enter or Space to play {C_WHITE}{C_BOLD}{cur_name}{C_RESET} ")
        sys.stdout.write("\n".join(lines))
        sys.stdout.flush()

    render()

    while True:
        k = get_key()
        if not k:
            time.sleep(0.02)
            continue

        if k in HOTKEY_MAP:
            idx = HOTKEY_MAP[k]
            selected_idx = idx
            render()
            time.sleep(0.08)
            games[idx]["fn"]()
            render()
        elif k in ("up", "w"):
            selected_idx = (selected_idx - 1) % len(games)
            render()
        elif k in ("down", "s"):
            selected_idx = (selected_idx + 1) % len(games)
            render()
        elif k in ("left", "a"):
            if selected_idx >= 6:
                selected_idx -= 6
            else:
                selected_idx = (selected_idx - 1) % len(games)
            render()
        elif k in ("right", "d"):
            if selected_idx < 6:
                selected_idx += 6
            else:
                selected_idx = (selected_idx + 1) % len(games)
            render()
        elif k in ("enter", " "):
            games[selected_idx]["fn"]()
            render()
        elif k in ("q", "escape"):
            clear_screen()
            show_cursor()
            print(f"{C_GREEN}Thanks for playing Daybook 8-Bit Arcade!{C_RESET}\n")
            return


if __name__ == "__main__":
    try:
        arcade_menu()
    except KeyboardInterrupt:
        pass
    finally:
        show_cursor()
        print()
