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

        # neighbor directionality Rules

        # Masyu Rules using neighbor directionality
        # For fire stones: neighbors must be perpendicular (one vertical, one horizontal)
        # For ice stones: neighbors must be collinear (both horizontal or both vertical)

        for fireCol, fireRow in fireStonePositions:
            # Get valid neighbors
            neighborsList = []
            if fireCol > 0:
                neighborsList.append((fireCol - 1, fireRow))
            if fireCol < grid_size[1] - 1:
                neighborsList.append((fireCol + 1, fireRow))
            if fireRow > 0:
                neighborsList.append((fireCol, fireRow - 1))
            if fireRow < grid_size[0] - 1:
                neighborsList.append((fireCol, fireRow + 1))

            # Fire stone must have exactly 2 marked neighbors
            markedNeighbors = [grid[nc][nr] for nc, nr in neighborsList]
            fireNeighborCount = sum([If(n != 0, 1, 0) for n in markedNeighbors])
            s.add(fireNeighborCount == 2)

            # Fire rule: neighbors must be perpendicular
            # If we have 2 neighbors, they must be in different directions (one col-aligned, one row-aligned)
            horizontalNeighbors = []
            verticalNeighbors = []

            for nc, nr in neighborsList:
                if nr == fireRow:  # Same row = horizontal neighbor
                    horizontalNeighbors.append((nc, nr))
                if nc == fireCol:  # Same column = vertical neighbor
                    verticalNeighbors.append((nc, nr))

            # Fire stone needs at least one horizontal and one vertical marked neighbor
            if horizontalNeighbors and verticalNeighbors:
                hNarked = Or(*[grid[nc][nr] != 0 for nc, nr in horizontalNeighbors])
                vMarked = Or(*[grid[nc][nr] != 0 for nc, nr in verticalNeighbors])
                s.add(And(hNarked, vMarked))

        # For ice stones: neighbors must be collinear (straight through or turn on sides)
        for iceCol, iceRow in iceStonePositions:
            neighborsList = []
            if iceCol > 0:
                neighborsList.append((iceCol - 1, iceRow))
            if iceCol < grid_size[1] - 1:
                neighborsList.append((iceCol + 1, iceRow))
            if iceRow > 0:
                neighborsList.append((iceCol, iceRow - 1))
            if iceRow < grid_size[0] - 1:
                neighborsList.append((iceCol, iceRow + 1))

            # Ice stone must have exactly 2 marked neighbors
            markedNeighbors = [grid[nc][nr] for nc, nr in neighborsList]
            iceNeighborCount = sum([If(n != 0, 1, 0) for n in markedNeighbors])
            s.add(iceNeighborCount == 2)

            # Ice rule: neighbors must be collinear (both horizontal OR both vertical)
            horizontalNeighbors = []
            verticalNeighbors = []

            for nc, nr in neighborsList:
                if nr == iceRow:  # Same row = horizontal
                    horizontalNeighbors.append((nc, nr))
                if nc == iceCol:  # Same column = vertical
                    verticalNeighbors.append((nc, nr))

            # Either both horizontal or both vertical marked
            hNarked = [grid[nc][nr] != 0 for nc, nr in horizontalNeighbors]
            vMarked = [grid[nc][nr] != 0 for nc, nr in verticalNeighbors]

            if hNarked:
                bothH = And(*hNarked) if len(hNarked) == 2 else hNarked[0]
            else:
                bothH = False

            if vMarked:
                bothV = And(*vMarked) if len(vMarked) == 2 else vMarked[0]
            else:
                bothV = False

            s.add(Or(bothH, bothV))

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
