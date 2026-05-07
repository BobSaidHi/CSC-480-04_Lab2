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
        # cached solution
        if len(self.solution) > 0:
            return self.solution.pop(0)

        # gather info
        fireStones = state.get_all_tile_locations(FireStone)
        iceStones = state.get_all_tile_locations(IceStone)
        gridSize = state.grid_size
        wizardLocation = state.active_entity_location

        firePositions = {(s.row, s.col) for s in fireStones}
        icePositions = {(s.row, s.col) for s in iceStones}
        allStonePositions = firePositions | icePositions

        def inBounds(r, c):
            return 0 <= r < gridSize[0] and 0 <= c < gridSize[1]

        def neighbors(pos):
            r, c = pos
            ns = []
            if inBounds(r - 1, c):
                ns.append((r - 1, c))
            if inBounds(r + 1, c):
                ns.append((r + 1, c))
            if inBounds(r, c - 1):
                ns.append((r, c - 1))
            if inBounds(r, c + 1):
                ns.append((r, c + 1))
            return ns

        def dirBetween(a, b):
            ar, ac = a
            br, bc = b
            if br < ar:
                return "up"
            if br > ar:
                return "down"
            if bc < ac:
                return "left"
            return "right"

        def isTurn(a, b, c):
            return dirBetween(a, b) != dirBetween(b, c)

        def isStraight(a, b, c):
            return dirBetween(a, b) == dirBetween(b, c)

        # Build a connected-cycle Z3 model directly on grid edges.
        s = Solver()
        s.set("timeout", 60000)

        start = (wizardLocation.row, wizardLocation.col)
        rows, cols = gridSize

        openCells = []
        for r in range(rows):
            for c in range(cols):
                tile = state.tile_grid[r][c]
                if tile.__class__.__name__ != "Wall":
                    openCells.append((r, c))

        openSet = set(openCells)
        if start not in openSet:
            return WizardMoves.STAY

        def edgeKey(a, b):
            return (a, b) if a < b else (b, a)

        edgeVars = {}
        for (r, c) in openCells:
            for (nr, nc) in neighbors((r, c)):
                if (nr, nc) in openSet:
                    k = edgeKey((r, c), (nr, nc))
                    if k not in edgeVars:
                        edgeVars[k] = Int(f"e_{k[0][0]}_{k[0][1]}_{k[1][0]}_{k[1][1]}")
                        s.add(Or(edgeVars[k] == 0, edgeVars[k] == 1))

        selected = {}
        for cell in openCells:
            selected[cell] = Int(f"sel_{cell[0]}_{cell[1]}")
            s.add(Or(selected[cell] == 0, selected[cell] == 1))

        # Stones and start must be part of the loop.
        s.add(selected[start] == 1)
        for cell in allStonePositions:
            if cell not in openSet:
                return WizardMoves.STAY
            s.add(selected[cell] == 1)

        # Bound loop size to keep solving tractable.
        totalSelected = z3.Sum([selected[c] for c in openCells])
        s.add(totalSelected >= len(allStonePositions) + 1)
        s.add(totalSelected <= min(len(openCells), 92))

        def edgeVal(a, b):
            if a not in openSet or b not in openSet:
                return 0
            k = edgeKey(a, b)
            if k not in edgeVars:
                return 0
            return edgeVars[k]

        # Degree is 2 for selected cells, 0 otherwise.
        for cell in openCells:
            degExpr = 0
            for nb in neighbors(cell):
                if nb in openSet:
                    degExpr = degExpr + edgeVal(cell, nb)
            s.add(degExpr == 2 * selected[cell])

        # Connectivity is enforced lazily: solve, detect disconnected cycles, add cut constraints.
        def continueStraightFromStone(stoneCell, dirR, dirC):
            nr, nc = stoneCell[0] + dirR, stoneCell[1] + dirC
            rr, rc = stoneCell[0] + 2 * dirR, stoneCell[1] + 2 * dirC
            if (nr, nc) not in openSet or (rr, rc) not in openSet:
                return 0
            return edgeVal((nr, nc), (rr, rc))

        # Masyu constraints matching game.py's checks.
        for cell in firePositions:
            up = edgeVal(cell, (cell[0] - 1, cell[1]))
            down = edgeVal(cell, (cell[0] + 1, cell[1]))
            left = edgeVal(cell, (cell[0], cell[1] - 1))
            right = edgeVal(cell, (cell[0], cell[1] + 1))

            # Fire: must turn at the stone.
            s.add(up + down != 2)
            s.add(left + right != 2)

            # Fire: must be straight directly before and after the turn.
            s.add(Implies(up == 1, continueStraightFromStone(cell, -1, 0) == 1))
            s.add(Implies(down == 1, continueStraightFromStone(cell, 1, 0) == 1))
            s.add(Implies(left == 1, continueStraightFromStone(cell, 0, -1) == 1))
            s.add(Implies(right == 1, continueStraightFromStone(cell, 0, 1) == 1))

        for cell in icePositions:
            up = edgeVal(cell, (cell[0] - 1, cell[1]))
            down = edgeVal(cell, (cell[0] + 1, cell[1]))
            left = edgeVal(cell, (cell[0], cell[1] - 1))
            right = edgeVal(cell, (cell[0], cell[1] + 1))

            vertical = And(up == 1, down == 1)
            horizontal = And(left == 1, right == 1)

            # Ice: must go straight through.
            s.add(Or(vertical, horizontal))

            upCont = continueStraightFromStone(cell, -1, 0)
            downCont = continueStraightFromStone(cell, 1, 0)
            leftCont = continueStraightFromStone(cell, 0, -1)
            rightCont = continueStraightFromStone(cell, 0, 1)

            # Ice: must turn directly before or after.
            s.add(Implies(vertical, Not(And(upCont == 1, downCont == 1))))
            s.add(Implies(horizontal, Not(And(leftCont == 1, rightCont == 1))))

        selectedEdges = set()
        maxConnectivityCuts = 120
        cutRound = 0
        while cutRound < maxConnectivityCuts:
            checkResult = s.check()
            if checkResult != z3.sat:
                print("Connected-cycle Z3 model unsat or timeout")
                return WizardMoves.STAY

            m = s.model()
            selectedEdges = set()
            for (a, b), ev in edgeVars.items():
                val = int(str(m.evaluate(ev, model_completion=True)))
                if val == 1:
                    selectedEdges.add((a, b))

            adj = {}
            for cell in openCells:
                adj[cell] = []
            for (a, b) in selectedEdges:
                adj[a].append(b)
                adj[b].append(a)

            # Build components over selected cells only.
            selectedCells = set()
            for cell in openCells:
                if len(adj[cell]) > 0:
                    selectedCells.add(cell)

            if start not in selectedCells:
                s.add(selected[start] == 1)
                cutRound += 1
                continue

            comps = []
            seen = set()
            for cell in selectedCells:
                if cell in seen:
                    continue
                stack = [cell]
                comp = set([cell])
                seen.add(cell)
                while stack:
                    cur = stack.pop()
                    for nb in adj[cur]:
                        if nb not in seen:
                            seen.add(nb)
                            comp.add(nb)
                            stack.append(nb)
                comps.append(comp)

            startComp = None
            for comp in comps:
                if start in comp:
                    startComp = comp
                    break

            if startComp is not None and allStonePositions.issubset(startComp) and len(comps) == 1:
                break

            # Add subtour-elimination cuts for disconnected components not containing start.
            for comp in comps:
                if start in comp:
                    continue
                boundary = []
                for cell in comp:
                    for nb in neighbors(cell):
                        if nb in openSet and nb not in comp:
                            ev = edgeVal(cell, nb)
                            if isinstance(ev, int):
                                continue
                            boundary.append(ev)
                if len(boundary) == 0:
                    print("Disconnected component cannot be connected; unsat")
                    return WizardMoves.STAY
                s.add(z3.Sum(boundary) >= 2)

            cutRound += 1

        if cutRound >= maxConnectivityCuts:
            print("Failed to connect cycle components in time")
            return WizardMoves.STAY

        # Build cycle adjacency and walk once around the loop.
        cycleAdj = {}
        for c in openCells:
            cycleAdj[c] = []
        for (a, b) in selectedEdges:
            cycleAdj[a].append(b)
            cycleAdj[b].append(a)

        if len(cycleAdj[start]) != 2:
            print("Z3 produced invalid start degree")
            return WizardMoves.STAY

        foundPath = [start]
        prev = None
        cur = start
        safety = 0
        while True:
            safety += 1
            if safety > len(openCells) + 5:
                print("Failed to reconstruct cycle path")
                return WizardMoves.STAY

            nextOptions = cycleAdj[cur]
            if len(nextOptions) != 2:
                print("Invalid cycle degree during reconstruction")
                return WizardMoves.STAY

            nxt = nextOptions[0] if nextOptions[0] != prev else nextOptions[1]
            foundPath.append(nxt)
            prev = cur
            cur = nxt
            if cur == start:
                break

        # convert to moves
        for i in range(len(foundPath) - 1):
            r1, c1 = foundPath[i]
            r2, c2 = foundPath[i + 1]
            if r2 < r1:
                self.solution.append(WizardMoves.UP)
            elif r2 > r1:
                self.solution.append(WizardMoves.DOWN)
            elif c2 < c1:
                self.solution.append(WizardMoves.LEFT)
            elif c2 > c1:
                self.solution.append(WizardMoves.RIGHT)

        if self.solution:
            return self.solution.pop(0)

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
