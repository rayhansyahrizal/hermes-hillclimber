"""Terminal replay renderer."""

from hillclimber.judge import Puzzle, RouteResult


def render_result(puzzle: Puzzle, result: RouteResult) -> str:
    grid = [list(row) for row in puzzle.rows]
    for row, col in result.visited:
        if grid[row][col] != "#":
            grid[row][col] = "*"
    row, col = result.final_position
    grid[row][col] = "@"
    board = "\n".join("".join(line) for line in grid)
    status = (
        f"score={result.score}  treasures={result.treasures_collected}/{len(puzzle.treasures)}  "
        f"steps={result.steps}  exit={'yes' if result.reached_exit else 'no'}  "
        f"collision={'yes' if result.collided else 'no'}"
    )
    return f"{board}\n{status}\n{result.feedback}"
