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

    def react(self, state: GameState) -> WizardMoves:
        fire_stones = state.get_all_tile_locations(FireStone)
        ice_stones = state.get_all_tile_locations(IceStone)
        grid_size = state.grid_size
        wizard_location = state.active_entity_location

        # TODO: YOUR CODE HERE
        return MASYU_1_SOLUTION.pop(0)


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
