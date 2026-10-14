#!/usr/bin/env python3
"""
8-BIT RETRO TERMINAL ARCADE
100% Offline • Zero External Dependencies • Pure Python & ANSI
Games: Snake, Pong, Galactica (Space Invaders), Breakout
"""
import atexit
import json
import os
import random
import sys
import time
from pathlib import Path

# Enable ANSI escape sequences on Windows console
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
    return {"snake": 0, "pong": 0, "galactica": 0, "breakout": 0}


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
            # ANSI escape sequence (e.g. \x1b[A for arrow keys in modern emulators)
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

        # Check collision with walls or self
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

        # Render frame
        grid = [[" " for _ in range(WIDTH)] for _ in range(HEIGHT)]
        # Borders
        for x in range(WIDTH):
            grid[0][x] = "═"
            grid[HEIGHT - 1][x] = "═"
        for y in range(HEIGHT):
            grid[y][0] = "║"
            grid[y][WIDTH - 1] = "║"
        grid[0][0], grid[0][WIDTH - 1] = "╔", "╗"
        grid[HEIGHT - 1][0], grid[HEIGHT - 1][WIDTH - 1] = "╚", "╝"

        # Food
        fx, fy = food
        grid[fy][fx] = f"{C_RED}★{C_RESET}"

        # Snake
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
    # Game Over screen
    sys.stdout.write(f"\n  {C_RED}{C_BOLD}GAME OVER!{C_RESET} Score: {score}  (Press any key to return to menu)")
    sys.stdout.flush()
    while True:
        k = get_key()
        if k is not None:
            break
        time.sleep(0.05)


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

        # AI tracking for P2
        if random.random() < 0.85:
            if by < p2_pos + pad_h // 2 and p2_pos > 1:
                p2_pos -= 1
            elif by > p2_pos + pad_h // 2 and p2_pos < HEIGHT - pad_h - 1:
                p2_pos += 1

        # Ball movement
        bx += vx
        by += vy

        # Bounce off top & bottom
        if by <= 1:
            by = 1
            vy = -vy
        elif by >= HEIGHT - 2:
            by = HEIGHT - 2
            vy = -vy

        # Left paddle collision
        if int(bx) == 2 and p1_pos <= int(by) < p1_pos + pad_h:
            vx = abs(vx) * 1.05
            vy += (int(by) - (p1_pos + pad_h / 2)) * 0.3
        # Right paddle collision
        elif int(bx) == WIDTH - 3 and p2_pos <= int(by) < p2_pos + pad_h:
            vx = -abs(vx) * 1.05
            vy += (int(by) - (p2_pos + pad_h / 2)) * 0.3

        # Goal scored
        if bx <= 0:
            score_p2 += 1
            bx, by = WIDTH // 2, HEIGHT // 2
            vx, vy = 1, random.choice([-0.6, 0.6])
            time.sleep(0.4)
        elif bx >= WIDTH - 1:
            score_p1 += 1
            bx, by = WIDTH // 2, HEIGHT // 2
            vx, vy = -1, random.choice([-0.6, 0.6])
            time.sleep(0.4)

        # Draw Court
        grid = [[" " for _ in range(WIDTH)] for _ in range(HEIGHT)]
        for x in range(WIDTH):
            grid[0][x] = "═"
            grid[HEIGHT - 1][x] = "═"
        for y in range(HEIGHT):
            grid[y][WIDTH // 2] = "┆"

        # Draw Paddles
        for i in range(pad_h):
            if 0 <= p1_pos + i < HEIGHT:
                grid[p1_pos + i][1] = f"{C_CYAN}█{C_RESET}"
            if 0 <= p2_pos + i < HEIGHT:
                grid[p2_pos + i][WIDTH - 2] = f"{C_MAGENTA}█{C_RESET}"

        # Draw Ball
        ibx, iby = max(1, min(WIDTH - 2, int(bx))), max(1, min(HEIGHT - 2, int(by)))
        grid[iby][ibx] = f"{C_YELLOW}●{C_RESET}"

        frame = [f"\033[H{C_CYAN}╔═[ 🏓 RETRO PONG ]════════════════════════════════════╗{C_RESET}",
                 f"  {C_CYAN}YOU: {score_p1}{C_RESET}                      {C_MAGENTA}CPU: {score_p2}{C_RESET}     {C_GRAY}(First to 5 wins · W/S to move){C_RESET}"]
        for row in grid:
            frame.append("  " + "".join(row))
        sys.stdout.write("\n".join(frame) + "\n")
        sys.stdout.flush()
        time.sleep(0.04)

    save_score("pong", score_p1)
    winner = f"{C_GREEN}YOU WON! 🎉{C_RESET}" if score_p1 >= max_score else f"{C_RED}CPU WON! 🤖{C_RESET}"
    sys.stdout.write(f"\n  {C_BOLD}MATCH OVER!{C_RESET} {winner} (Press any key to return to menu)")
    sys.stdout.flush()
    while True:
        k = get_key()
        if k is not None:
            break
        time.sleep(0.05)


# ==============================================================================
# GAME 3: 🚀 GALACTICA (SPACE INVADERS)
# ==============================================================================
def play_galactica():
    WIDTH, HEIGHT = 50, 20
    player_x = WIDTH // 2
    bullets = []       # [(x, y)]
    alien_bombs = []   # [(x, y)]
    aliens = []        # [(x, y, type)]
    lives = 3
    score = 0
    high_score = load_scores().get("galactica", 0)

    # Spawn 3 rows of aliens
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
        elif k in (" ", "up", "w") and now - last_shot > 0.22:
            bullets.append([player_x, HEIGHT - 3])
            last_shot = now

        # Move bullets
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
            if not hit and by > 1:
                new_bullets.append([bx, by])
        bullets = new_bullets

        # Move alien fleet
        if now - last_fleet_move > fleet_speed:
            last_fleet_move = now
            edge_hit = False
            for a in aliens:
                if (fleet_dir == 1 and a["x"] >= WIDTH - 5) or (fleet_dir == -1 and a["x"] <= 2):
                    edge_hit = True
                    break
            if edge_hit:
                fleet_dir *= -1
                for a in aliens:
                    a["y"] += 1
                fleet_speed = max(0.12, fleet_speed * 0.94)  # Speeds up as they descend!
            else:
                for a in aliens:
                    a["x"] += fleet_dir

            # Aliens fire bombs
            if random.random() < 0.6 and aliens:
                shooter = random.choice(aliens)
                alien_bombs.append([shooter["x"] + 1, shooter["y"] + 1])

        # Move alien bombs
        new_bombs = []
        for bx, by in alien_bombs:
            by += 1
            if by >= HEIGHT - 2 and abs(bx - player_x) <= 2:
                lives -= 1
                # Flash red
                sys.stdout.write("\033[41m \033[0m")
            elif by < HEIGHT - 1:
                new_bombs.append([bx, by])
        alien_bombs = new_bombs

        # Check invasion landing
        if any(a["y"] >= HEIGHT - 3 for a in aliens):
            lives = 0
            break

        # Render frame
        grid = [[" " for _ in range(WIDTH)] for _ in range(HEIGHT)]
        for x in range(WIDTH):
            grid[0][x] = "═"
            grid[HEIGHT - 1][x] = "═"
        for y in range(HEIGHT):
            grid[y][0] = "║"
            grid[y][WIDTH - 1] = "║"

        # Draw Aliens
        for a in aliens:
            ax, ay = a["x"], a["y"]
            icon = ["{C_MAGENTA}W{C_RESET}", "{C_CYAN}M{C_RESET}", "{C_YELLOW}V{C_RESET}"][a["type"]]
            if 0 < ay < HEIGHT - 1 and 0 < ax < WIDTH - 3:
                grid[ay][ax] = icon
                grid[ay][ax + 1] = icon

        # Draw Bullets
        for bx, by in bullets:
            if 0 < by < HEIGHT - 1 and 0 < bx < WIDTH - 1:
                grid[by][bx] = f"{C_GREEN}│{C_RESET}"

        # Draw Bombs
        for bx, by in alien_bombs:
            if 0 < by < HEIGHT - 1 and 0 < bx < WIDTH - 1:
                grid[by][bx] = f"{C_RED}▼{C_RESET}"

        # Draw Player
        px = player_x
        py = HEIGHT - 2
        grid[py][px - 1] = f"{C_CYAN}▲{C_RESET}"
        grid[py][px] = f"{C_WHITE}{C_BOLD}═{C_RESET}"
        grid[py][px + 1] = f"{C_CYAN}▲{C_RESET}"

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
    sys.stdout.write(f"\n  {C_BOLD}MISSION ENDED!{C_RESET} {result} Final Score: {score} (Press any key to return to menu)")
    sys.stdout.flush()
    while True:
        k = get_key()
        if k is not None:
            break
        time.sleep(0.05)


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

    # Bricks grid: row 2 to 5
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

        # Ball movement
        bx += vx
        by += vy

        # Walls bounce
        if bx <= 1:
            bx = 1
            vx = abs(vx)
        elif bx >= WIDTH - 2:
            bx = WIDTH - 2
            vx = -abs(vx)
        if by <= 1:
            by = 1
            vy = abs(vy)

        # Paddle bounce
        if int(by) == HEIGHT - 2 and pad_x <= int(bx) <= pad_x + pad_w:
            vy = -abs(vy)
            hit_offset = (bx - (pad_x + pad_w / 2)) / (pad_w / 2)
            vx = hit_offset * 1.2
            if abs(vx) < 0.3:
                vx = 0.5 if vx >= 0 else -0.5

        # Check brick collision
        ibx, iby = int(bx), int(by)
        for (brick_x, brick_y), (bcolor, bpts) in list(bricks.items()):
            if brick_y == iby and brick_x <= ibx < brick_x + 4:
                del bricks[(brick_x, brick_y)]
                score += bpts
                vy = -vy
                break

        # Ball lost
        if by >= HEIGHT - 1:
            lives -= 1
            bx, by = pad_x + pad_w // 2, HEIGHT - 4
            vx, vy = random.choice([0.8, -0.8]), -0.7
            time.sleep(0.4)

        # Draw frame
        grid = [[" " for _ in range(WIDTH)] for _ in range(HEIGHT)]
        for x in range(WIDTH):
            grid[0][x] = "═"
            grid[HEIGHT - 1][x] = "═"
        for y in range(HEIGHT):
            grid[y][0] = "║"
            grid[y][WIDTH - 1] = "║"

        # Draw Bricks
        for (brick_x, brick_y), (bcolor, _) in bricks.items():
            for i in range(4):
                if brick_x + i < WIDTH - 1:
                    grid[brick_y][brick_x + i] = f"{bcolor}█{C_RESET}"

        # Draw Paddle
        for i in range(pad_w):
            if pad_x + i < WIDTH - 1:
                grid[HEIGHT - 2][pad_x + i] = f"{C_CYAN}▀{C_RESET}"

        # Draw Ball
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
    sys.stdout.write(f"\n  {C_BOLD}{msg}{C_RESET} Score: {score} (Press any key to return to menu)")
    sys.stdout.flush()
    while True:
        k = get_key()
        if k is not None:
            break
        time.sleep(0.05)


# ==============================================================================
# MAIN ARCADE MENU
# ==============================================================================
def arcade_menu():
    hide_cursor()
    selected_idx = 0

    games = [
        {"num": "1", "name": "🐍 Snake", "desc": "Eat, grow, survive", "key": "snake", "fn": play_snake},
        {"num": "2", "name": "🏓 Pong", "desc": "Classic 1v1 vs CPU", "key": "pong", "fn": play_pong},
        {"num": "3", "name": "🚀 Galactica", "desc": "Alien invasion shooter", "key": "galactica", "fn": play_galactica},
        {"num": "4", "name": "🧱 Breakout", "desc": "Smash colorful bricks", "key": "breakout", "fn": play_breakout},
        {"num": "Q", "name": "🚪 Exit", "desc": "Return to terminal", "key": None, "fn": None},
    ]

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
            f"          {C_YELLOW}★ 8-BIT TERMINAL RETRO GAMING ★{C_RESET}",
            f"      {C_GRAY}100% Offline • No Internet • Pure Retro Arcade{C_RESET}",
            "",
            f"  {C_WHITE}{C_BOLD}SELECT A GAME:{C_RESET}",
            "",
        ]

        for i, g in enumerate(games):
            is_sel = (i == selected_idx)
            ptr = f"{C_YELLOW}{C_BOLD}►{C_RESET}" if is_sel else " "
            bracket = f"{C_YELLOW}[{g['num']}]{C_RESET}" if is_sel else f"{C_CYAN}[{g['num']}]{C_RESET}"
            name = f"{C_WHITE}{C_BOLD}{g['name']:<14}{C_RESET}" if is_sel else f"{C_WHITE}{g['name']:<14}{C_RESET}"
            desc = f"{C_YELLOW}{g['desc']:<26}{C_RESET}" if is_sel else f"{C_GRAY}{g['desc']:<26}{C_RESET}"
            score_txt = f"{C_YELLOW}Best: {scores.get(g['key'], 0)}{C_RESET}" if g["key"] else ""
            lines.append(f"  {ptr} {bracket} {name} {desc} {score_txt}")

        lines.append("")
        lines.append(f"  {C_GRAY}Controls: {C_WHITE}[↑/↓]{C_GRAY} or {C_WHITE}[W/S]{C_GRAY} to browse  •  {C_WHITE}[Enter/Space]{C_GRAY} to Play  •  {C_WHITE}[1-4]{C_GRAY} Instant  •  {C_WHITE}[Q]{C_GRAY} Exit{C_RESET}")
        lines.append("")
        lines.append(f"  {C_YELLOW}► Select with arrow keys + Enter, or press 1-4 directly:{C_RESET} ")
        sys.stdout.write("\n".join(lines))
        sys.stdout.flush()

    render()

    while True:
        k = get_key()
        if not k:
            time.sleep(0.02)
            continue

        if k in ("1", "2", "3", "4"):
            idx = int(k) - 1
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
        elif k in ("enter", " "):
            if selected_idx == 4 or games[selected_idx]["fn"] is None:
                clear_screen()
                show_cursor()
                print(f"{C_GREEN}Thanks for playing Daybook 8-Bit Arcade!{C_RESET}\n")
                return
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
