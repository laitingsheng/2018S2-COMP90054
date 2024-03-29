# minimax.py
# ---------
# Licensing Information:  You are free to use or extend these projects for
# educational purposes provided that (1) you do not distribute or publish
# solutions, (2) you retain this notice, and (3) you provide clear
# attribution to UC Berkeley, including a link to http://ai.berkeley.edu.
#
# Attribution Information: The Pacman AI projects were developed at UC Berkeley.
# The core projects and autograders were primarily created by John DeNero
# (denero@cs.berkeley.edu) and Dan Klein (klein@cs.berkeley.edu).
# Student side autograding was added by Brad Miller, Nick Hay, and
# Pieter Abbeel (pabbeel@cs.berkeley.edu).

from __future__ import division, print_function

import random
from heapq import heappop, heappush
from operator import itemgetter

from captureAgents import CaptureAgent
from game import Actions, Directions


################################################################################
# Constants
################################################################################
inf = float("inf")


################################################################################
# Team creation
################################################################################
def createTeam(
    firstIndex,
    secondIndex,
    isRed,
    first='AbuseMonteCarloAgent',
    second='AbuseMonteCarloAgent',
):
    return [
        eval(first)(firstIndex, isRed, False),
        eval(second)(secondIndex, isRed, True)
    ]


################################################################################
# Mixed Agents
################################################################################
class AbuseMonteCarloAgent(CaptureAgent, object):
    """
    This is a class define an offensive agent which use A* to initiate an
    optimal path to eat all food, and use Monte Carlo to escape from the chasers
    if the chaser is within the visible range
    """

    _instances = [None, None]

    def __init__(self, index, red, defense, timeForComputing=.1):
        CaptureAgent.__init__(self, index, timeForComputing)
        object.__init__(self)

        self.red = red
        self._defense = defense
        self._height = self._width = self._half = self._bound = \
            self._actions = self._escapes = None
        self._prevCarry = 0
        self._recompute = False
        self._escape = False

        # record each instance created
        self._instances[index // 2] = self

    def registerInitialState(self, gameState):
        """
        Initialise the agent and compute an initial route
        """
        CaptureAgent.registerInitialState(self, gameState)

        data = gameState.data
        layout = data.layout
        height = self._height = layout.height
        width = self._width = layout.width
        self._half = half = width // 2
        red = self.red
        bound = half - 1 if red else half
        walls = layout.walls
        self._bound = set(
            (bound, y) for y in xrange(height) if not walls[bound][y]
        )

        # only offensive agent needs to compute the route
        if not self._defense:
            self._computeRoute(gameState)

    def _computeRoute(self, gameState):
        data = gameState.data
        foods = data.food.data
        height, width, half = self._height, self._width, self._half
        red = self.red
        # deliver the food to the bound to gain actual score
        bounds = self._bound
        foods = set(
            (x, y)
            for x in (xrange(half, width) if red else xrange(half))
            for y in xrange(height)
            if foods[x][y]
        )
        distancer = self.distancer

        # Dijkstra (or variant of Uniform Cost Search) implementation
        pos = data.agentStates[self.index].configuration.pos
        path = []
        q = [(0, pos, path, foods)]
        while q:
            dist, pos, path, fs = heappop(q)

            if pos in bounds and not fs:
                break

            if fs:
                npos, ndist = min(
                    ((np, dist + distancer.getDistance(pos, np)) for np in fs),
                    key=itemgetter(1)
                )

                nfs = fs.copy()
                nfs.remove(npos)
                heappush(q, (ndist, npos, path + [npos], nfs))
            else:
                npos, ndist = min(
                    (
                        (np, dist + distancer.getDistance(pos, np))
                        for np in bounds
                    ),
                    key=itemgetter(1)
                )
                heappush(q, (ndist, npos, path + [npos], None))
        # reverse the path to utilise the efficiency of list.pop
        path.reverse()

        self._actions = path

    def observationFunction(self, gameState):
        """
        Abuse this function to obtain a full game state from the controller
        """
        return gameState

    def chooseAction(self, gameState):
        """
        Choose an action based on the current status of the agent
        """

        return self.defenseAction(gameState) \
            if self._defense \
            else self.offenseAction(gameState)

    def _target(self, gameState, target):
        index = self.index
        agentStates = gameState.data.agentStates
        agent = agentStates[index]
        food = agentStates[target]

        penalty = 2 if agent.scaredTimer > 0 else 0
        fpos = food.configuration.pos

        distancer = self.distancer
        successors = [
            (a, gameState.generateSuccessor(index, a))
            for a in gameState.getLegalActions(index)
            if a != Directions.STOP
        ]
        successors = [
            (a, successor)
            for a, successor in successors
            if not successor.data.agentStates[index].isPacman
        ]
        dist = [
            (
                a, distancer.getDistance(
                    succ.data.agentStates[index].configuration.pos, fpos
                )
            ) for a, succ in successors
        ]
        dist = [(d, a) for a, d in dist if d >= penalty]

        minval = min(dist)[0]
        return random.choice([a for d, a in dist if d == minval])

    def defenseAction(self, gameState):
        """
        Choose a defensive action
        """
        index = self.index
        red = self.red
        data = gameState.data
        agentStates = data.agentStates
        agentState = agentStates[index]
        pos = agentState.configuration.pos
        distancer = self.distancer

        nt = 0
        t = None
        pnc = 0
        target = []
        for i in (gameState.blueTeam if red else gameState.redTeam):
            agentState = agentStates[i]
            nc = agentState.numCarrying
            if nc > 0:
                nt += 1
                if nc > pnc:
                    pnc = nc
                    t = i
            target.append((i, agentState))

        if nt > 0:
            return self._target(gameState, t)

        dist = [
            (
                i,
                -a.isPacman,
                distancer.getDistance(
                    pos, a.configuration.pos
                )
            )
            for i, a in target
        ]

        return self._target(gameState, min(dist, key=itemgetter(1, 2))[0])

    def _computeEscape(self, gameState):
        index = self.index
        data = gameState.data
        agentStates = data.agentStates
        bounds = self._bound
        distancer = self.distancer

        _recompute = not self._escape
        walls = data.layout.walls.data
        for i in (gameState.blueTeam if self.red else gameState.redTeam):
            agentState = agentStates[i]
            if not agentState.isPacman:
                x, y = agentState.configuration.pos
                pos = x, y = int(x), int(y)
                if self._escapes is None or pos in self._escapes:
                    _recompute = True
                walls[x + 1][y] = walls[x][y + 1] = walls[x - 1][y] = \
                    walls[x][y - 1] = walls[x][y] = True

        agent = agentStates[index]
        x, y = pos = tuple(map(int, agent.configuration.pos))
        if not _recompute:
            nx, ny = self._escapes.pop()
            return Actions.vectorToDirection((nx - x, ny - y))

        # A* to escape
        path = []
        h = min(distancer.getDistance(pos, b) for b in bounds)
        q = [(h, h, 0, pos, path)]
        escaped = False
        visited = set()
        while q:
            _, _, g, pos, path = heappop(q)

            if pos in bounds:
                escaped = True
                break

            visited.add(pos)

            x, y = pos
            for dx, dy in ((0, 1), (1, 0), (0, -1), (-1, 0)):
                npos = nx, ny = x + dx, y + dy
                if not walls[nx][ny] and npos not in visited:
                    h = min(distancer.getDistance(npos, b) for b in bounds)
                    ng = g + 1
                    heappush(q, (ng + h, h, ng, npos, path + [npos]))

        if not escaped:
            self._defense = True
            teammate = self._instances[(index // 2 + 1) % 2]
            teammate._defense = False
            teammate._computeRoute(gameState)
            return Directions.STOP

        path.reverse()
        x, y = agent.configuration.pos
        nx, ny = path.pop()
        if not path:
            self._escape = False

        return Actions.vectorToDirection((nx - x, ny - y))

    def _eval(self, gameState, index, red):
        fs = [0] * 6

        data = gameState.data
        agentStates = data.agentStates
        agent = agentStates[index]
        pos = agent.configuration.pos
        distancer = self.distancer

        # current score
        fs[0] = data.score

        for i in gameState.redTeam:
            agentState = agentStates[i]
            if red:
                fs[1] += agentState.numCarrying
            else:
                if (
                    agent.isPacman and
                    not agentState.isPacman and
                    agentState.scaredTimer == 0
                ):
                    fs[2] += distancer.getDistance(
                        pos, agentState.configuration.pos
                    )
                if agentState.scaredTimer > 0:
                    fs[3] += 1
        for i in gameState.blueTeam:
            agentState = agentStates[i]
            if red:
                if (
                    agent.isPacman and
                    not agentState.isPacman and
                    agentState.scaredTimer == 0
                ):
                    fs[2] += distancer.getDistance(
                        pos, agentState.configuration.pos
                    )
                if agentState.scaredTimer > 0:
                    fs[3] += 1
            else:
                fs[1] += agentState.numCarrying

        fs[4] = agent.isPacman

        if agent.numCarrying > 0:
            fs[5] = min(distancer.getDistance(b, pos) for b in self._bound)

        weights = [10000, 5, 2, 1, 100, -10]
        return sum(f * w for f, w in zip(fs, weights))

    def _minimax(self, gameState, depth):
        index = self.index

        actions = gameState.getLegalActions(index)
        actions.remove(Directions.STOP)
        nindex = (index + 1) % 4
        ndepth = depth - 1
        nred = not self.red
        alpha = -inf
        a = []
        for action in actions:
            re = self._min(
                gameState.generateSuccessor(index, action),
                ndepth,
                nindex,
                nred,
                alpha,
                inf
            )
            if re > alpha:
                alpha = re
                a = [action]
            elif re == alpha:
                a.append(action)

        return random.choice(a)

    def _min(self, gameState, depth, index, red, alpha, beta):
        if depth < 1:
            return self._eval(gameState, index, red)

        actions = gameState.getLegalActions(index)
        actions.remove(Directions.STOP)
        nindex = (index + 1) % 4
        ndepth = depth - 1
        nred = not self.red
        for action in actions:
            re = self._max(
                gameState.generateSuccessor(index, action),
                ndepth,
                nindex,
                nred,
                alpha,
                beta
            )
            if re < beta:
                beta = re
                if beta <= alpha:
                    return beta

        return beta

    def _max(self, gameState, depth, index, red, alpha, beta):
        if depth < 1:
            return self._eval(gameState, index, red)

        actions = gameState.getLegalActions(index)
        actions.remove(Directions.STOP)
        nindex = (index + 1) % 4
        ndepth = depth - 1
        nred = not self.red
        for action in actions:
            re = self._min(
                gameState.generateSuccessor(index, action),
                ndepth,
                nindex,
                nred,
                alpha,
                beta
            )
            if re > alpha:
                alpha = re
                if alpha >= beta:
                    return beta

        return alpha

    def offenseAction(self, gameState):
        """
        Choose an offensive action based on current circumstance, could either
        be the followings
        * following the route
        * escape if in danger
        """
        if self._escape:
            return self._computeEscape(gameState)

        index = self.index
        red = self.red
        agentStates = gameState.data.agentStates
        agentState = agentStates[index]

        distancer = self.distancer
        pos = agentState.configuration.pos
        states = [
            agentStates[i]
            for i in (gameState.blueTeam if red else gameState.redTeam)
        ]
        if any(
            not s.isPacman and s.scaredTimer == 0 and distancer.getDistance(
                s.configuration.pos, pos
            ) < 6
            for s in states
        ):
            self._recompute = True
            nc = self._prevCarry = agentState.numCarrying
            if nc > 0:
                self._escape = True
                return self._computeEscape(gameState)
            return self._minimax(gameState, 12)

        if self._recompute or self._prevCarry > agentState.numCarrying:
            self._computeRoute(gameState)
            self._recompute = False
        self._prevCarry = agentState.numCarrying

        actions = self._actions
        if agentState.configuration.pos == actions[-1]:
            actions.pop()
        cdest = actions[-1]
        return min(
            (
                (
                    a,
                    distancer.getDistance(gameState.generateSuccessor(
                        index, a
                    ).data.agentStates[index].configuration.pos, cdest)
                )
                for a in gameState.getLegalActions(index)
            ),
            key=itemgetter(1)
        )[0]
