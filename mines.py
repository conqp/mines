#! /usr/bin/env python3
"""A mine sweeping game."""

from __future__ import annotations
from argparse import ArgumentParser, Namespace
from dataclasses import dataclass
from enum import Enum, auto
from os import linesep
from random import sample
from string import digits, ascii_lowercase
from sys import exit, stderr    # pylint: disable=W0622
from typing import Iterable, Iterator, NamedTuple, Optional, Union
from warnings import warn

try:
    import readline     # pylint: disable=W0611
except ModuleNotFoundError:
    warn('Module "readline" is not available. Limited console functionality.')


__all__ = [
    'NUM_TO_STR',
    'STR_TO_NUM',
    'GameOver',
    'Vector2D',
    'Cell',
    'Minefield',
    'ActionType',
    'Action',
    'read_action',
    'get_args',
    'play_round',
    'main'
]


NUM_TO_STR = dict(enumerate(digits + ascii_lowercase))
STR_TO_NUM = {value: key for key, value in NUM_TO_STR.items()}
USAGE = '''Visit fields:
    $ <x> <y>

Toggle flags:
    $ ? <x> <y>'''


class Returncode(Enum):
    """Available returncodes."""

    WON = 0
    LOST = 1
    INVALID_PARAMETER = 2
    USER_ABORT = 3

    def __int__(self) -> int:
        return self.value


class GameOver(Exception, Enum):
    """Indicates that the game has ended."""

    LOST = ('You stepped onto a mine. :(', Returncode.LOST)
    WON = ('All mines cleared. Great job.', Returncode.WON)

    def __init__(self, message: str, returncode: Returncode):
        super().__init__(message)
        self.message = message
        self.returncode = returncode

    def __int__(self) -> int:
        return int(self.returncode)

    def __str__(self) -> str:
        return self.message


class Vector2D(NamedTuple):
    """A 2D coordinate on a grid."""

    x: int
    y: int

    @classmethod
    def from_strings(cls, strings: Iterable[str]) -> Vector2D:
        """Creates a coordinate from an iterable of strings."""
        try:
            return cls(*map(lambda pos: STR_TO_NUM[pos], strings))
        except KeyError as error:
            raise ValueError(f'Invalid coordinate value: {error}') from None
        except TypeError:
            raise ValueError('Expect two coordinates: x and y') from None

    @property
    def neighbors(self) -> Iterator[Vector2D]:
        """Yield fields surrounding this position."""
        for delta_y in range(-1, 2):
            for delta_x in range(-1, 2):
                if delta_x == delta_y == 0:
                    continue    # Skip the current position itself.

                yield type(self)(self.x + delta_x, self.y + delta_y)


@dataclass
class Cell:
    """A cell of a minefield."""

    position: Vector2D
    mine: Optional[bool] = None
    flagged: bool = False
    visited: bool = False

    def toggle_flag(self) -> None:
        """Toggles the flag on this field."""
        if self.visited:
            return

        self.flagged = not self.flagged


class Minefield:
    """A minefield."""

    def __init__(self, width: int, height: int, mines: int):
        super().__init__()

        if width < 1 or height < 1:
            raise ValueError('Field is too small.')

        if width > (maxsize := len(NUM_TO_STR)) or height > maxsize:
            raise ValueError(f'Max field width and height are {maxsize}.')

        if mines < 0:
            raise ValueError('Amount of mines cannot be negative.')

        if mines >= width * height:
            raise ValueError('Too many mines for mine field.')

        self.mines = mines
        self._grid = [
            [Cell(Vector2D(x, y)) for x in range(width)] for y in range(height)
        ]
        self._result = None

    def __str__(self) -> str:
        """Returns a string representation of the minefield."""
        return linesep.join(self._lines)

    def __iter__(self) -> Iterator[Cell]:
        """Yields all cells of the minefield."""
        return (cell for row in self._grid for cell in row)

    def __contains__(self, item: Union[Cell, Vector2D]) -> bool:
        if isinstance(item, Cell):
            return item.position in self

        return 0 <= item.x < self.width and 0 <= item.y < self.height

    def __getitem__(self, position: Vector2D) -> Cell:
        """Returns the cell at the given position."""
        if position in self:
            return self._grid[position.y][position.x]

        raise IndexError(position)

    @property
    def _header(self) -> Iterator[str]:
        """Returns the table header."""
        row = ' '.join(NUM_TO_STR[index] for index in range(self.width))
        yield f' |{row}| '
        yield ''.join(['-+', '-' * (self.width * 2 - 1), '+-'])

    @property
    def _lines(self) -> Iterator[str]:
        """Yield lines of the str representation."""
        yield from (header := list(self._header))

        for pos_y, row in enumerate(self._grid):
            prefix = NUM_TO_STR[pos_y]
            row = ' '.join(self._cell_to_str(cell) for cell in row)
            yield f'{prefix}|{row}|{prefix}'

        yield from reversed(header)

    @property
    def _uninitialized(self) -> bool:
        """Check whether all cells are uninitalized."""
        return all(cell.mine is None for cell in self)

    @property
    def _uninitialized_cells(self) -> list[Cell]:
        """Yield cells that have not been initialized."""
        return [cell for cell in self if cell.mine is None]

    @property
    def flags(self) -> int:
        """Returns the amount of flags set."""
        return sum(cell.flagged for cell in self)

    @property
    def remaining_mines(self) -> int:
        """Return the amount of remaining mines."""
        return self.mines - self.flags

    @property
    def width(self) -> int:
        """Returns the width of the field."""
        return len(self._grid[0])

    @property
    def height(self) -> int:
        """Returns the height of the field."""
        return len(self._grid)

    def _neighbors(self, position: Vector2D) -> Iterator[Cell]:
        """Yield cells surrounding the given position."""
        return filter(None, map(self.get, position.neighbors))

    def _unvisited_neighbors(self, position: Vector2D) -> Iterator[Cell]:
        """Yield cells surrounding the given position that are unvisited."""
        return filter(lambda cell: not cell.visited, self._neighbors(position))

    def _neighboring_mines(self, position: Vector2D) -> int:
        """Return the amount of mines surrounding the given position."""
        return sum(cell.mine for cell in self._neighbors(position))

    def _neighboring_flags(self, position: Vector2D) -> int:
        """Return the amount of flags surrounding the given position."""
        return sum(cell.flagged for cell in self._neighbors(position))

    def _remaining_neighboring_mines(self, position: Vector2D) -> int:
        """Return the amount of remaining mines
        surrounding the given position.
        """
        return max([
            0, self._neighboring_mines(position)
            - self._neighboring_flags(position)
        ])

    def _cell_to_str(self, cell: Cell) -> str:
        """Return a str representation of the cell."""
        if cell.flagged:
            return '?' if self._result is None else ('!' if cell.mine else 'x')

        if cell.mine and cell.visited:
            return '*'

        if cell.mine and self._result is not None:
            return 'o'

        if not cell.mine and (cell.visited or self._result is not None):
            if surrounding_mines := self._neighboring_mines(cell.position):
                return str(surrounding_mines)

            return ' '

        return '■'

    def _initialize(self, start: Vector2D) -> None:
        """Inistialize the mine field."""
        # Ensure that we do not step on a mine on our first visit.
        self[start].mine = False

        for cell in sample(self._uninitialized_cells, k=self.mines):
            cell.mine = True

        for cell in self._uninitialized_cells:
            cell.mine = False

    def _end_game(self, result: GameOver) -> None:
        """Ends the game."""
        self._result = result
        raise result

    def _visit_cell(self, cell: Cell) -> None:
        """Visits the given cell."""
        if cell.visited or cell.flagged:
            return

        cell.visited = True

        if cell.mine:
            self._end_game(GameOver.LOST)
        elif all(cell.visited for cell in self if not cell.mine):
            self._end_game(GameOver.WON)

    def _visit_neighbors(self, position: Vector2D) -> None:
        """Visits the neighbors of the given position."""
        unvisited = list(self._unvisited_neighbors(position))

        while unvisited:
            self._visit_cell(cell := unvisited.pop())

            if not self._neighboring_mines(cell.position):
                unvisited.extend(self._unvisited_neighbors(cell.position))

    def get(self, position: Vector2D) -> Optional[Cell]:
        """Returns the cell at the given coordinate,
        if is on the minefield or else None.
        """
        return self._grid[position.y][position.x] if position in self else None

    def toggle_flag(self, position: Vector2D) -> None:
        """Toggles the marker on the given cell."""
        self[position].toggle_flag()

    def visit(self, position: Vector2D) -> None:
        """Visit the cell at the given position."""
        if self._result is not None:
            raise self._result

        if self._uninitialized:
            self._initialize(position)

        self._visit_cell(self[position])

        if not self._remaining_neighboring_mines(position):
            self._visit_neighbors(position)


class ActionType(Enum):
    """Game actions."""

    FLAG = auto()
    VISIT = auto()


class Action(NamedTuple):
    """An action on a coordinate."""

    action: ActionType
    position: Vector2D

    @classmethod
    def from_strings(cls, items: list[str]) -> Action:
        """Creates an action from a list of strings."""
        coordinates = [item for item in items if item in STR_TO_NUM.keys()]
        position = Vector2D.from_strings(coordinates)

        try:
            action, *excess = filter(lambda i: i not in coordinates, items)
        except ValueError:
            return cls(ActionType.VISIT, position)

        if excess:
            raise ValueError('Must specify at most one action.')

        if action == '?':
            return cls(ActionType.FLAG, position)

        raise ValueError(f'Action not recognized: {action}')

    @classmethod
    def from_string(cls, text: str) -> Action:
        """Parses an action from a string."""
        return cls.from_strings(text.strip().split())


def read_action(prompt: str = 'Enter action and coordinate: ') -> Action:
    """Reads an Action."""

    while True:
        try:
            text = input(prompt)
        except EOFError:
            print()
            continue

        try:
            return Action.from_string(text)
        except ValueError as error:
            print(error)


def get_args(description: str = __doc__) -> Namespace:
    """Parses the command line arguments."""

    parser = ArgumentParser(description=description)
    parser.add_argument('-x', '--width', type=int, metavar='x', default=8)
    parser.add_argument('-y', '--height', type=int, metavar='y', default=8)
    parser.add_argument('-m', '--mines', type=int, metavar='n', default=10)
    parser.add_argument('-u', '--usage', action='store_true')
    return parser.parse_args()


def play_round(minefield: Minefield) -> None:
    """Play a round."""

    print(minefield)
    action = read_action()

    if action.action == ActionType.FLAG:
        minefield.toggle_flag(action.position)
    else:
        minefield.visit(action.position)


def main() -> int:
    """Run the minesweeper game."""

    args = get_args()

    if args.usage:
        print(USAGE)
        return 0

    try:
        minefield = Minefield(args.width, args.height, args.mines)
    except ValueError as error:
        print(error, file=stderr)
        return int(Returncode.INVALID_PARAMETER)

    while True:
        try:
            play_round(minefield)
        except IndexError:
            print('Coordinates must lie on the minefield.', file=stderr)
        except KeyboardInterrupt:
            print('\nAborted by user.')
            return int(Returncode.USER_ABORT)
        except GameOver as game_over:
            print(minefield)
            print(game_over)
            return int(game_over)


if __name__ == '__main__':
    exit(main())
