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
        # return solution if available
        # return MASYU_1_SOLUTION.pop(0)
        if len(self.solution) > 0:
            return self.solution.pop(0)
        # else: Solve

        # Gather info
        fire_stones = state.get_all_tile_locations(FireStone)
        ice_stones = state.get_all_tile_locations(IceStone)
        grid_size = state.grid_size
        wizard_location = state.active_entity_location

        grid_size = state.grid_size
        wizard_location = state.active_entity_location

        # Enumerated Constants
        NOT_VISITED = 0
        START = 1
        FIRE_TURN = 2
        ICE_STRAIGHT = 3

        # Build Constraints
        s = Solver()
        s.set("timeout", 60000)

        # Get fire stone positions
        fireStonePositions = []
        for i in fire_stones:
            fireStonePositions.append((i.row, i.col))

        # Get ice stone positions
        iceStonePositions = []
        for i in ice_stones:
            iceStonePositions.append((i.row, i.col))

        # Build Z3 grid
        grid = []
        for colJ in range(grid_size[1]):
            row = []
            for rowI in range(grid_size[0]):
                row.append(Int(f"{colJ}_{rowI}"))
            grid.append(row)

        # Add locations of interest to grid
        for colJ in range(grid_size[1]):
            for rowI in range(grid_size[0]):
                if colJ == wizard_location.col and rowI == wizard_location.row:
                    s.add(grid[colJ][rowI] == START)
                elif (colJ, rowI) in fireStonePositions:
                    s.add(grid[colJ][rowI] == FIRE_TURN)
                elif (colJ, rowI) in iceStonePositions:
                    s.add(grid[colJ][rowI] == ICE_STRAIGHT)
                else:  # Unconstrained cell
                    s.add(
                        Or(
                            grid[colJ][rowI] == NOT_VISITED,
                            grid[colJ][rowI] == START,
                            grid[colJ][rowI] == FIRE_TURN,
                            grid[colJ][rowI] == ICE_STRAIGHT,
                        )
                    )

        # Visited cells must connect
        for colJ in range(grid_size[1]):
            for rowI in range(grid_size[0]):
                cell = grid[colJ][rowI]
                neighbors = []

                if colJ > 0:
                    neighbors.append(grid[colJ - 1][rowI])
                if colJ < grid_size[1] - 1:
                    neighbors.append(grid[colJ + 1][rowI])
                if rowI > 0:
                    neighbors.append(grid[colJ][rowI - 1])
                if rowI < grid_size[0] - 1:
                    neighbors.append(grid[colJ][rowI + 1])

                # Count visited neighbors
                visitedCount = 0
                for n in neighbors:
                    visitedCount = visitedCount + If(n != 0, 1, 0)
                s.add(Implies(cell != 0, visitedCount == 2))

        # Be sure not to skip any stones
        for col, row in fireStonePositions:
            s.add(grid[col][row] != NOT_VISITED)
        for col, row in iceStonePositions:
            s.add(grid[col][row] != NOT_VISITED)

        # Actually follow the fire turns and ice straights
        def getDirection(cell1, cell2):
            """Get direction from cell1 to cell2: 0=UP, 1=DOWN, 2=LEFT, 3=RIGHT"""
            c1, r1 = cell1
            c2, r2 = cell2
            if c2 > c1:
                return 0  # RIGHT
            elif c2 < c1:
                return 1  # LEFT
            elif r2 > r1:
                return 2  # DOWN
            else:
                return 3  # UP

        # For each fire stone, enforce turn rule (3 consecutive positions must show a direction change)
        for fireCol, fireRow in fireStonePositions:
            neighbors = []
            if fireCol > 0:
                neighbors.append((fireCol - 1, fireRow))
            if fireCol < grid_size[1] - 1:
                neighbors.append((fireCol + 1, fireRow))
            if fireRow > 0:
                neighbors.append((fireCol, fireRow - 1))
            if fireRow < grid_size[0] - 1:
                neighbors.append((fireCol, fireRow + 1))

            # Fire stone must have exactly 2 neighbors that are marked
            fireNeighborCount = 0
            for nc, nr in neighbors:
                fireNeighborCount = fireNeighborCount + If(grid[nc][nr] != 0, 1, 0)
            s.add(fireNeighborCount == 2)

        # For each ice stone, enforce straight rule (must go straight through, turn on sides)
        for iceCol, iceRow in iceStonePositions:
            neighbors = []
            if iceCol > 0:
                neighbors.append(((iceCol - 1, iceRow), "left"))
            if iceCol < grid_size[1] - 1:
                neighbors.append(((iceCol + 1, iceRow), "right"))
            if iceRow > 0:
                neighbors.append(((iceCol, iceRow - 1), "up"))
            if iceRow < grid_size[0] - 1:
                neighbors.append(((iceCol, iceRow + 1), "down"))

            # Ice stone must have exactly 2 neighbors
            iceNeighborCount = 0
            for (nc, nr), _ in neighbors:
                iceNeighborCount = iceNeighborCount + If(grid[nc][nr] != 0, 1, 0)
            s.add(iceNeighborCount == 2)

        # Solve
        match s.check():
            case z3.unknown:
                print("Solver returned unknown")
            case z3.unsat:
                print("Solver returned unsat")
            case z3.sat:
                print("Solver returned sat")
                m = s.model()

                # Build solution steps from visited cells
                visitedCells = []
                for colJ in range(grid_size[1]):
                    for rowI in range(grid_size[0]):
                        val = int(
                            str(m.evaluate(grid[colJ][rowI], model_completion=True))
                        )
                        if val != 0:
                            visitedCells.append(((colJ, rowI), val))

                if len(visitedCells) < 0:
                    print("No visited cells found in model")
                    return WizardMoves.STAY

                # Find starting position
                startPos = None
                for pos, val in visitedCells:
                    if val == START:
                        startPos = pos
                        break

                print(f"Total marked cells: {len(visitedCells)}")
                print(
                    f"Fire stones: {len(fireStonePositions)}, Ice stones: {len(iceStonePositions)}"
                )
                print(
                    f"Total stones: {len(fireStonePositions) + len(iceStonePositions)}"
                )

                # Walk the path and convert to moves
                print("Walking solution path...")

                if startPos is None:
                    print("ERROR: No START position found")
                    return WizardMoves.STAY

                currentPos = startPos
                visited = set()
                pathPositions = [currentPos]
                visited.add(currentPos)

                while len(visited) < len(visitedCells):
                    colJ, rowI = currentPos
                    foundNext = False

                    # Check all 4 neighbors
                    for nextCol, nextRow in [
                        (colJ - 1, rowI),
                        (colJ + 1, rowI),
                        (colJ, rowI - 1),
                        (colJ, rowI + 1),
                    ]:
                        if (nextCol, nextRow) not in visited:
                            # Check if this neighbor is marked
                            for pos, val in visitedCells:
                                if pos == (nextCol, nextRow):
                                    pathPositions.append((nextCol, nextRow))
                                    visited.add((nextCol, nextRow))
                                    currentPos = (nextCol, nextRow)
                                    foundNext = True
                                    break
                    if not foundNext:
                        print(
                            f"ERROR: Could not find next cell. Visited {len(visited)}/{len(visitedCells)}"
                        )
                        break

                # Convert path positions to moves
                print("Converting path to moves...")
                for i in range(len(pathPositions) - 1):
                    col1, row1 = pathPositions[i]
                    col2, row2 = pathPositions[i + 1]

                    if col2 > col1:
                        self.solution.append(WizardMoves.RIGHT)
                    elif col2 < col1:
                        self.solution.append(WizardMoves.LEFT)
                    elif row2 > row1:
                        self.solution.append(WizardMoves.DOWN)
                    elif row2 < row1:
                        self.solution.append(WizardMoves.UP)

                if self.solution:
                    print("Found solution: " + str(self.solution))
                    return self.solution.pop(0)


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
