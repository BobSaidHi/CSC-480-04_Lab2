from model import (
    Location,
    Wizard,
    IceStone,
    FireStone,
    WizardMoves,
    GameAction,
    GameState,
    WizardSpells, NeutralStone,
)
from agents import WizardAgent

import z3
from z3 import (Solver, Bool, Bools, Int, Ints, Or, Not, And, Implies, Distinct,
                If)


class PuzzleWizard(WizardAgent):
    # Python doesn't have static variables, but I guess we can just put them here instead
    solved = False
    solution = []

    def react(self, state: GameState) -> WizardMoves:
        fire_stones = state.get_all_tile_locations(FireStone)
        ice_stones = state.get_all_tile_locations(IceStone)
        grid_size = state.grid_size
        wizard_location = state.active_entity_location

        # DONE: YOUR CODE HERE
        # return MASYU_1_SOLUTION.pop(0)#
        
        # Assuming system will stop after solved
        if(self.solved):
            print("Returning solution move: ", self.solution[0])
            return self.solution.pop(0)

        # Else: Solve

        # Describe path
        print("Describing path with z3 variables...")
        minPathLen = len(fire_stones) * 2 + len(ice_stones) * 2 + 1
        maxPathLen = grid_size[0] * grid_size[1]
        for pathLen in range(minPathLen, maxPathLen):
            print("Trying path length: ", pathLen)
            s = Solver()

            problemPath = []
            for i in range(pathLen):
                rowZ3Int, colZ3Int = Int(f"r_{pathLen}_{i}"), Int(f"c_{pathLen}_{i}")
                cellZ3Int = Int(f"cell_{pathLen}_{i}")
                problemPath.append((rowZ3Int, colZ3Int, cellZ3Int))
                s.add(cellZ3Int == rowZ3Int * grid_size[1] + colZ3Int)
                
            # Build constraints
            for i in range(pathLen - 1):
                row1, col1, cell1 = problemPath[i]
                row2, col2, cell2 = problemPath[i + 1]

                # Each step may involve one move (Cardinal directions only)
                # print("Adding movement constraints for step ", i)
                s.add(Or(
                    And(row2 == row1 + 1, cell2 == col1),  # DOWN
                    And(row2 == row1 - 1, cell2 == col1),  # UP
                    And(row2 == row1, cell2 == col1 + 1),  # RIGHT
                    And(row2 == row1, cell2 == col1 - 1),  # LEFT
                ))

            # Start from the wizard's initial location
            print("Adding starting location constraint")
            s.add(And(
                problemPath[0][0] == wizard_location.row,
                problemPath[0][1] == wizard_location.col,
            ))
            
            # Stay in bounds
            print("Adding bounds constraints")
            for i in range(pathLen):
                row1, col1, cell1 = problemPath[i]

                # print("Adding bounds constraints for step ", i)
                s.add(And(row1 >= 0, row1 < grid_size[0], col1 >= 0, col1 < grid_size[1]))
            
            # Don't revisit locations
            print("Adding non-revisiting constraints")
            # Add by cell number to save on compute
            cells = []
            for i in range(pathLen - 1):
                for j in range(i + 1, pathLen - 1):
                    # print("Adding non-revisiting constraint for ", problemPath[i][2])
                    cells.append(problemPath[i][2])
            # Distinct is variadic, unpack the cells list into arguments
            s.add(Distinct(*cells))
                    
            # Return to start
            rowStart, colStart, cellStart = problemPath[0]
            rowEnd, colEnd, cellEnd = problemPath[pathLen - 1]
            print("Adding return to start constraint")
            s.add(And(rowEnd == rowStart, colEnd == colStart))

            # Helpers
            def getRowDelta(i):
                return problemPath[i + 1][0] - problemPath[i][0]

            def getColDelta(i):
                return problemPath[i + 1][1] - problemPath[i][1]

            def makeStraightConstraint(i, j):
                return And(getRowDelta(i) == getRowDelta(j), getColDelta(i) == getColDelta(j))

            def makeTurnConstraint(i, j):
                return Or(
                    And(getRowDelta(i) == 0, getColDelta(i) != 0, getRowDelta(j) != 0, getColDelta(j) == 0),
                    And(getRowDelta(i) != 0, getColDelta(i) == 0, getRowDelta(j) == 0, getColDelta(j) != 0),
                )

            # Fire stone constraints
            print("Adding fire stone constraints...")
            for stone_loc in fire_stones:
                stonesOnPath = []

                # Must visit all fire stones
                for i in range(pathLen):
                    row, col, cell = problemPath[i]
                    stonesOnPath.append(And(row == stone_loc.row, col == stone_loc.col))
                # print("Adding fire stone constraint for stone at ", stone_loc)
                s.add(Or(*stonesOnPath))

                # Must move straight through fire stones (no turns)
                fireStones = []
                for k in range(2, pathLen - 2):
                    fireStones.append(And(
                        problemPath[k][0] == stone_loc.row,
                        problemPath[k][1] == stone_loc.col,
                        makeStraightConstraint(k - 2, k - 1),   # straight before stone
                        makeTurnConstraint(k - 1, k),           # turn at stone
                        makeStraightConstraint(k, k + 1),       # straight after stone
                    ))
                s.add(Or(*fireStones))

            # Ice stone constraints
            print("Adding ice stone constraints...")
            for stone_loc in ice_stones:
                # Must visit all ice stones
                stonesOnPath = []
                for i in range(pathLen):
                    row, col, cell = problemPath[i]
                    stonesOnPath.append(And(row == stone_loc.row, col == stone_loc.col))
                # print("Adding ice stone constraint for stone at ", stone_loc)
                s.add(Or(*stonesOnPath))

                # Must turn on ice stones (no straight moves)
                iceStones = []
                for k in range(2, pathLen - 2):
                    iceStones.append(And(
                        problemPath[k][0] == stone_loc.row,
                        problemPath[k][1] == stone_loc.col,
                        makeStraightConstraint(k - 1, k),       # straight through stone
                        Or(
                            Not(makeStraightConstraint(k - 2, k - 1)),
                            Not(makeStraightConstraint(k, k + 1)),
                        )                          # turn on one side
                    ))
                s.add(Or(*iceStones))
            
            # Process into solution
            print("Solving with z3...")
            match s.check():
                case z3.unsat:
                    print("No solution found!\n")
                    continue
                    # return WizardMoves.STAY
                case z3.sat:
                    print("Solution found!")
                    
                    self.solved = True
                    m = s.model()

                    # Convert z3 solution to a path
                    solutionPath = []
                    for i in range(pathLen):
                        rVal = int(str(m.evaluate(problemPath[i][0])))
                        cVal = int(str(m.evaluate(problemPath[i][1])))
                        solutionPath.append(Location(row=rVal, col=cVal))
                    
                    # Convert path to moves
                    for i in range(len(solutionPath) - 1):
                        curr = solutionPath[i]
                        nextLoc = solutionPath[i + 1]
                        
                        deltaRow = nextLoc.row - curr.row
                        deltaCol = nextLoc.col - curr.col
                        
                        if deltaRow == 1:
                            self.solution.append(WizardMoves.DOWN)
                        elif deltaRow == -1:
                            self.solution.append(WizardMoves.UP)
                        elif deltaCol == 1:
                            self.solution.append(WizardMoves.RIGHT)
                        elif deltaCol == -1:
                            self.solution.append(WizardMoves.LEFT)

                    print("Solution moves: ", self.solution)
                    
                    print("Returning first move: ", self.solution[0])
                    return self.solution.pop(0)
        print("No solution found for any path length :(\n")
        return WizardMoves.STAY

class SpellCastingPuzzleWizard(WizardAgent):

    def react(self, state: GameState) -> GameAction:
        fire_stones = state.get_all_tile_locations(FireStone)
        ice_stones = state.get_all_tile_locations(IceStone)
        neutral_stones = state.get_all_tile_locations(NeutralStone)

        grid_size = state.grid_size
        wizard_location = state.active_entity_location

        # TODO: YOUR CODE HERE
        return MASYU_2_SOLUTION.pop(0)


"""
Here are some reference solutions for some of the included puzzle maps you 
can use to help you test things
"""

MASYU_1_SOLUTION = [WizardMoves.RIGHT, WizardMoves.UP, WizardMoves.RIGHT,
                    WizardMoves.RIGHT, WizardMoves.RIGHT, WizardMoves.RIGHT,
                    WizardMoves.DOWN, WizardMoves.LEFT, WizardMoves.LEFT,
                    WizardMoves.DOWN, WizardMoves.DOWN, WizardMoves.DOWN,
                    WizardMoves.RIGHT, WizardMoves.UP, WizardMoves.UP,
                    WizardMoves.RIGHT, WizardMoves.RIGHT, WizardMoves.RIGHT,
                    WizardMoves.DOWN, WizardMoves.LEFT, WizardMoves.LEFT,
                    WizardMoves.DOWN, WizardMoves.DOWN, WizardMoves.DOWN,
                    WizardMoves.RIGHT, WizardMoves.RIGHT, WizardMoves.UP,
                    WizardMoves.UP, WizardMoves.RIGHT, WizardMoves.UP,
                    WizardMoves.UP, WizardMoves.UP, WizardMoves.LEFT,
                    WizardMoves.LEFT, WizardMoves.UP, WizardMoves.RIGHT,
                    WizardMoves.RIGHT, WizardMoves.RIGHT, WizardMoves.DOWN,
                    WizardMoves.DOWN, WizardMoves.DOWN, WizardMoves.DOWN,
                    WizardMoves.DOWN, WizardMoves.LEFT, WizardMoves.DOWN,
                    WizardMoves.RIGHT, WizardMoves.DOWN, WizardMoves.DOWN,
                    WizardMoves.DOWN, WizardMoves.LEFT, WizardMoves.LEFT,
                    WizardMoves.LEFT, WizardMoves.LEFT, WizardMoves.UP,
                    WizardMoves.RIGHT, WizardMoves.RIGHT, WizardMoves.RIGHT,
                    WizardMoves.UP, WizardMoves.LEFT, WizardMoves.LEFT,
                    WizardMoves.LEFT, WizardMoves.LEFT, WizardMoves.DOWN,
                    WizardMoves.DOWN, WizardMoves.LEFT, WizardMoves.LEFT,
                    WizardMoves.UP, WizardMoves.UP, WizardMoves.UP,
                    WizardMoves.RIGHT, WizardMoves.RIGHT, WizardMoves.UP,
                    WizardMoves.LEFT, WizardMoves.LEFT, WizardMoves.LEFT,
                    WizardMoves.DOWN, WizardMoves.DOWN, WizardMoves.DOWN,
                    WizardMoves.LEFT, WizardMoves.UP, WizardMoves.UP,
                    WizardMoves.UP, WizardMoves.UP, WizardMoves.RIGHT,
                    WizardMoves.RIGHT, WizardMoves.UP, WizardMoves.UP,
                    WizardMoves.LEFT, WizardMoves.LEFT, WizardMoves.UP]

MASYU_2_SOLUTION = [WizardMoves.RIGHT, WizardSpells.FIREBALL, WizardMoves.DOWN,
                    WizardMoves.DOWN, WizardMoves.RIGHT, WizardMoves.UP,
                    WizardMoves.UP, WizardMoves.RIGHT, WizardMoves.DOWN,
                    WizardMoves.DOWN, WizardMoves.RIGHT, WizardMoves.RIGHT,
                    WizardMoves.RIGHT, WizardMoves.RIGHT, WizardMoves.UP,
                    WizardMoves.LEFT, WizardMoves.LEFT, WizardMoves.LEFT,
                    WizardMoves.UP, WizardMoves.RIGHT, WizardMoves.RIGHT,
                    WizardMoves.RIGHT, WizardMoves.RIGHT, WizardMoves.DOWN,
                    WizardMoves.DOWN, WizardMoves.DOWN, WizardMoves.DOWN,
                    WizardMoves.DOWN, WizardMoves.DOWN, WizardMoves.DOWN,
                    WizardMoves.DOWN, WizardMoves.DOWN, WizardMoves.LEFT,
                    WizardMoves.UP, WizardMoves.UP, WizardMoves.UP,
                    WizardMoves.LEFT, WizardMoves.LEFT, WizardMoves.DOWN,
                    WizardMoves.RIGHT, WizardMoves.DOWN, WizardMoves.DOWN,
                    WizardMoves.LEFT, WizardMoves.LEFT, WizardMoves.UP,
                    WizardMoves.UP, WizardMoves.UP, WizardMoves.UP,
                    WizardMoves.RIGHT, WizardMoves.UP, WizardMoves.RIGHT,
                    WizardMoves.RIGHT, WizardMoves.UP, WizardMoves.LEFT,
                    WizardMoves.LEFT, WizardMoves.LEFT, WizardMoves.DOWN,
                    WizardMoves.LEFT, WizardMoves.LEFT, WizardMoves.UP,
                    WizardMoves.LEFT, WizardMoves.DOWN, WizardMoves.DOWN,
                    WizardMoves.RIGHT, WizardMoves.RIGHT, WizardMoves.DOWN,
                    WizardSpells.FREEZE, WizardMoves.DOWN, WizardMoves.DOWN,
                    WizardMoves.DOWN, WizardMoves.LEFT, WizardMoves.LEFT,
                    WizardMoves.LEFT, WizardMoves.LEFT, WizardMoves.UP,
                    WizardMoves.RIGHT, WizardMoves.RIGHT, WizardMoves.RIGHT,
                    WizardMoves.UP, WizardMoves.UP, WizardMoves.LEFT,
                    WizardMoves.LEFT, WizardMoves.DOWN, WizardMoves.LEFT,
                    WizardMoves.UP, WizardMoves.UP, WizardMoves.RIGHT,
                    WizardMoves.UP, WizardMoves.UP, WizardMoves.UP,
                    WizardMoves.LEFT, WizardMoves.UP, WizardMoves.UP,
                    WizardSpells.FIREBALL, WizardMoves.RIGHT]
