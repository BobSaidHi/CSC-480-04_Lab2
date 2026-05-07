from unittest import case

from model import (
    Location,
    Wizard,
    IceStone,
    FireStone,
    WizardMoves,
    GameAction,
    GameState,
    WizardSpells,
    NeutralStone,
)
from agents import WizardAgent

import z3
from z3 import Solver, Bool, Bools, Int, Ints, Or, Not, And, Implies, Distinct, If


class PuzzleWizard(WizardAgent):
    solution = []

    def react(self, state: GameState) -> WizardMoves:
        # Return cached solution if available
        if len(self.solution) > 0:
            return self.solution.pop(0)

        # Gather info
        fire_stones = state.get_all_tile_locations(FireStone)
        ice_stones = state.get_all_tile_locations(IceStone)
        grid_size = state.grid_size
        wizard_location = state.active_entity_location

        # Constants for cell values
        NOT_VISITED = 0
        START = 1
        FIRE_TURN = 2
        ICE_STRAIGHT = 3

        s = Solver()
        s.set("timeout", 60000)

        # Get stone positions
        fire_positions = {(f.row, f.col) for f in fire_stones}
        ice_positions = {(i.row, i.col) for i in ice_stones}
        all_stones = fire_positions | ice_positions

        # Build Z3 grid (one variable per cell)
        grid = []
        for col in range(grid_size[1]):
            row = []
            for row_idx in range(grid_size[0]):
                row.append(Int(f"{col}_{row_idx}"))
            grid.append(row)

        # Assign cell types
        for col in range(grid_size[1]):
            for row_idx in range(grid_size[0]):
                if col == wizard_location.col and row_idx == wizard_location.row:
                    s.add(grid[col][row_idx] == START)
                elif (col, row_idx) in fire_positions:
                    s.add(grid[col][row_idx] == FIRE_TURN)
                elif (col, row_idx) in ice_positions:
                    s.add(grid[col][row_idx] == ICE_STRAIGHT)
                else:
                    s.add(Or(grid[col][row_idx] == NOT_VISITED, grid[col][row_idx] == START,
                            grid[col][row_idx] == FIRE_TURN, grid[col][row_idx] == ICE_STRAIGHT))

        # Path connectivity: marked cells must have exactly 2 marked neighbors
        for col in range(grid_size[1]):
            for row_idx in range(grid_size[0]):
                cell = grid[col][row_idx]
                neighbors = []
                if col > 0:
                    neighbors.append(grid[col - 1][row_idx])
                if col < grid_size[1] - 1:
                    neighbors.append(grid[col + 1][row_idx])
                if row_idx > 0:
                    neighbors.append(grid[col][row_idx - 1])
                if row_idx < grid_size[0] - 1:
                    neighbors.append(grid[col][row_idx + 1])

                marked_count = 0
                for n in neighbors:
                    marked_count = marked_count + If(n != 0, 1, 0)
                s.add(Implies(cell != 0, marked_count == 2))

        # Ensure all stones are in the path
        for col, row in fire_positions:
            s.add(grid[col][row] != NOT_VISITED)
        for col, row in ice_positions:
            s.add(grid[col][row] != NOT_VISITED)

        # Solve
        result = s.check()

        if result == z3.sat:
            m = s.model()

            # Extract marked cells
            marked_cells = set()
            cell_types = {}
            for col in range(grid_size[1]):
                for row_idx in range(grid_size[0]):
                    val = int(str(m.evaluate(grid[col][row_idx], model_completion=True)))
                    if val != NOT_VISITED:
                        marked_cells.add((col, row_idx))
                        cell_types[(col, row_idx)] = val

            print(f"Marked cells: {len(marked_cells)}, Stones: {len(all_stones)}")

            # DFS to find valid path satisfying Masyu rules
            def is_valid_path(path):
                """Check if path satisfies Masyu rules"""
                if len(path) < 2:
                    return False
                
                # Visit all stones
                visited_stones = sum(1 for pos in path if pos in all_stones)
                if visited_stones < len(all_stones):
                    return False

                # Check fire stone rules (must turn at fire, straight before/after)
                for i, pos in enumerate(path):
                    if pos in fire_positions:
                        if i < 1 or i >= len(path) - 1:
                            return False
                        # Get directions
                        prev_pos = path[i - 1]
                        next_pos = path[i + 1]
                        prev_dir = (pos[0] - prev_pos[0], pos[1] - prev_pos[1])
                        next_dir = (next_pos[0] - pos[0], next_pos[1] - pos[1])
                        # Must turn (directions differ)
                        if prev_dir == next_dir:
                            return False

                # Check ice stone rules (must go straight through)
                for i, pos in enumerate(path):
                    if pos in ice_positions:
                        if i < 1 or i >= len(path) - 1:
                            return False
                        prev_pos = path[i - 1]
                        next_pos = path[i + 1]
                        prev_dir = (pos[0] - prev_pos[0], pos[1] - prev_pos[1])
                        next_dir = (next_pos[0] - pos[0], next_pos[1] - pos[1])
                        # Must go straight (same direction)
                        if prev_dir != next_dir:
                            return False

                return True

            # DFS to find path
            def dfs(current, visited, path):
                if len(visited) == len(marked_cells):
                    # Check if we can return to start
                    if (wizard_location.col, wizard_location.row) in {(current[0] - (current[0] - wizard_location.col), current[1] - (current[1] - wizard_location.row))
                        for _ in [None]}:
                        # Try to close the loop
                        for next_col, next_row in [(current[0] - 1, current[1]), (current[0] + 1, current[1]),
                                                    (current[0], current[1] - 1), (current[0], current[1] + 1)]:
                            if (next_col, next_row) == (wizard_location.col, wizard_location.row):
                                closed_path = path + [(wizard_location.col, wizard_location.row)]
                                if is_valid_path(closed_path):
                                    return closed_path
                    return None

                # Try all marked neighbors
                col, row = current
                for next_col, next_row in [(col - 1, row), (col + 1, row), (col, row - 1), (col, row + 1)]:
                    if (next_col, next_row) in marked_cells and (next_col, next_row) not in visited:
                        visited.add((next_col, next_row))
                        result = dfs((next_col, next_row), visited, path + [(next_col, next_row)])
                        if result:
                            return result
                        visited.remove((next_col, next_row))

                return None

            # Start DFS from wizard location
            start = (wizard_location.col, wizard_location.row)
            found_path = dfs(start, {start}, [start])

            if found_path:
                print(f"Found valid path with {len(found_path)} positions")
                # Convert to moves
                for i in range(len(found_path) - 1):
                    col1, row1 = found_path[i]
                    col2, row2 = found_path[i + 1]

                    if col2 > col1:
                        self.solution.append(WizardMoves.RIGHT)
                    elif col2 < col1:
                        self.solution.append(WizardMoves.LEFT)
                    elif row2 > row1:
                        self.solution.append(WizardMoves.DOWN)
                    elif row2 < row1:
                        self.solution.append(WizardMoves.UP)

                if self.solution:
                    return self.solution.pop(0)

        print("Failed to find solution")
        return WizardMoves.STAY


class SpellCastingPuzzleWizard(WizardAgent):
    solution = []

    def react(self, state: GameState) -> GameAction:
        fire_stones = state.get_all_tile_locations(FireStone)
        ice_stones = state.get_all_tile_locations(IceStone)
        neutral_stones = state.get_all_tile_locations(NeutralStone)

        grid_size = state.grid_size
        wizard_location = state.active_entity_location

        # TODO: YOUR CODE HERE


"""
Here are some reference solutions for some of the included puzzle maps you 
can use to help you test things
"""

MASYU_1_SOLUTION = [
    WizardMoves.RIGHT,
    WizardMoves.UP,
    WizardMoves.RIGHT,
    WizardMoves.RIGHT,
    WizardMoves.RIGHT,
    WizardMoves.RIGHT,
    WizardMoves.DOWN,
    WizardMoves.LEFT,
    WizardMoves.LEFT,
    WizardMoves.DOWN,
    WizardMoves.DOWN,
    WizardMoves.DOWN,
    WizardMoves.RIGHT,
    WizardMoves.UP,
    WizardMoves.UP,
    WizardMoves.RIGHT,
    WizardMoves.RIGHT,
    WizardMoves.RIGHT,
    WizardMoves.DOWN,
    WizardMoves.LEFT,
    WizardMoves.LEFT,
    WizardMoves.DOWN,
    WizardMoves.DOWN,
    WizardMoves.DOWN,
    WizardMoves.RIGHT,
    WizardMoves.RIGHT,
    WizardMoves.UP,
    WizardMoves.UP,
    WizardMoves.RIGHT,
    WizardMoves.UP,
    WizardMoves.UP,
    WizardMoves.UP,
    WizardMoves.LEFT,
    WizardMoves.LEFT,
    WizardMoves.UP,
    WizardMoves.RIGHT,
    WizardMoves.RIGHT,
    WizardMoves.RIGHT,
    WizardMoves.DOWN,
    WizardMoves.DOWN,
    WizardMoves.DOWN,
    WizardMoves.DOWN,
    WizardMoves.DOWN,
    WizardMoves.LEFT,
    WizardMoves.DOWN,
    WizardMoves.RIGHT,
    WizardMoves.DOWN,
    WizardMoves.DOWN,
    WizardMoves.DOWN,
    WizardMoves.LEFT,
    WizardMoves.LEFT,
    WizardMoves.LEFT,
    WizardMoves.LEFT,
    WizardMoves.UP,
    WizardMoves.RIGHT,
    WizardMoves.RIGHT,
    WizardMoves.RIGHT,
    WizardMoves.UP,
    WizardMoves.LEFT,
    WizardMoves.LEFT,
    WizardMoves.LEFT,
    WizardMoves.LEFT,
    WizardMoves.DOWN,
    WizardMoves.DOWN,
    WizardMoves.LEFT,
    WizardMoves.LEFT,
    WizardMoves.UP,
    WizardMoves.UP,
    WizardMoves.UP,
    WizardMoves.RIGHT,
    WizardMoves.RIGHT,
    WizardMoves.UP,
    WizardMoves.LEFT,
    WizardMoves.LEFT,
    WizardMoves.LEFT,
    WizardMoves.DOWN,
    WizardMoves.DOWN,
    WizardMoves.DOWN,
    WizardMoves.LEFT,
    WizardMoves.UP,
    WizardMoves.UP,
    WizardMoves.UP,
    WizardMoves.UP,
    WizardMoves.RIGHT,
    WizardMoves.RIGHT,
    WizardMoves.UP,
    WizardMoves.UP,
    WizardMoves.LEFT,
    WizardMoves.LEFT,
    WizardMoves.UP,
]

MASYU_2_SOLUTION = [
    WizardMoves.RIGHT,
    WizardSpells.FIREBALL,
    WizardMoves.DOWN,
    WizardMoves.DOWN,
    WizardMoves.RIGHT,
    WizardMoves.UP,
    WizardMoves.UP,
    WizardMoves.RIGHT,
    WizardMoves.DOWN,
    WizardMoves.DOWN,
    WizardMoves.RIGHT,
    WizardMoves.RIGHT,
    WizardMoves.RIGHT,
    WizardMoves.RIGHT,
    WizardMoves.UP,
    WizardMoves.LEFT,
    WizardMoves.LEFT,
    WizardMoves.LEFT,
    WizardMoves.UP,
    WizardMoves.RIGHT,
    WizardMoves.RIGHT,
    WizardMoves.RIGHT,
    WizardMoves.RIGHT,
    WizardMoves.DOWN,
    WizardMoves.DOWN,
    WizardMoves.DOWN,
    WizardMoves.DOWN,
    WizardMoves.DOWN,
    WizardMoves.DOWN,
    WizardMoves.DOWN,
    WizardMoves.DOWN,
    WizardMoves.LEFT,
    WizardMoves.UP,
    WizardMoves.UP,
    WizardMoves.UP,
    WizardMoves.LEFT,
    WizardMoves.LEFT,
    WizardMoves.DOWN,
    WizardMoves.RIGHT,
    WizardMoves.DOWN,
    WizardMoves.DOWN,
    WizardMoves.LEFT,
    WizardMoves.LEFT,
    WizardMoves.UP,
    WizardMoves.UP,
    WizardMoves.UP,
    WizardMoves.UP,
    WizardMoves.RIGHT,
    WizardMoves.UP,
    WizardMoves.RIGHT,
    WizardMoves.RIGHT,
    WizardMoves.UP,
    WizardMoves.LEFT,
    WizardMoves.LEFT,
    WizardMoves.LEFT,
    WizardMoves.DOWN,
    WizardMoves.LEFT,
    WizardMoves.LEFT,
    WizardMoves.UP,
    WizardMoves.LEFT,
    WizardMoves.DOWN,
    WizardMoves.DOWN,
    WizardMoves.RIGHT,
    WizardMoves.RIGHT,
    WizardMoves.DOWN,
    WizardSpells.FREEZE,
    WizardMoves.DOWN,
    WizardMoves.DOWN,
    WizardMoves.DOWN,
    WizardMoves.LEFT,
    WizardMoves.LEFT,
    WizardMoves.LEFT,
    WizardMoves.LEFT,
    WizardMoves.UP,
    WizardMoves.RIGHT,
    WizardMoves.RIGHT,
    WizardMoves.RIGHT,
    WizardMoves.UP,
    WizardMoves.UP,
    WizardMoves.LEFT,
    WizardMoves.LEFT,
    WizardMoves.DOWN,
    WizardMoves.LEFT,
    WizardMoves.UP,
    WizardMoves.UP,
    WizardMoves.RIGHT,
    WizardMoves.UP,
    WizardMoves.UP,
    WizardMoves.UP,
    WizardMoves.LEFT,
    WizardMoves.UP,
    WizardMoves.UP,
    WizardSpells.FIREBALL,
    WizardMoves.RIGHT,
]
