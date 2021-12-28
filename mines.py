#! /usr/bin/env python3
"""A mine sweeping game."""

from __future__ import annotations
from argparse import ArgumentParser, Namespace
from dataclasses import dataclass
from enum import Enum
from os import linesep
from random import sample
from string import digits, ascii_lowercase
from sys import exit, stderr    # pylint: disable=W0622
from typing import Iterator, NamedTuple, Optional, Union
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


class Returncode(Enum):
    """Available returncodes."""

    USER_ABORT = 3
    INVALID_PARAMETER = 2
    LOST = 1
    WON = 0

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
    def from_strings(cls, strings: Iterator[str]) -> Vector2D:
        """Creates a coordinate from a set of strings."""
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
    marked: bool = False
    visited: bool = False

    def to_string(self, *, game_over: bool = False) -> str:
        """Returns a string representation."""
        if self.visited:
            return '*' if self.mine else ' '

        if self.marked:
            return ('!' if self.mine else 'x') if game_over else '?'

        if game_over and self.mine:
            return 'o'

        return ' ' if game_over else '■'

    def toggle_marker(self) -> None:
        """Toggles the marker on this field."""
        if self.visited:
            return

        self.marked = not self.marked


class PositionedCell(NamedTuple):
    """A coordinate / cell tuple."""

    position: Vector2D
    cell: Cell


class Minefield:
    """A mine field."""

    def __init__(self, width: int, height: int, mines: int):
        super().__init__()

        if width < 1 or height < 1:
            raise ValueError('Field is too small.')

        if width > (maxsize := len(NUM_TO_STR)) or height > maxsize:
            raise ValueError(f'Max field width and height are {maxsize}.')

        if mines >= (width * height - 1):
            raise ValueError('Too many mines for mine field.')

        self._mines = mines
        self._grid = [
            [Cell(Vector2D(x, y)) for x in range(width)] for y in range(height)
        ]
        self._game_over = None

    def __str__(self) -> str:
        """Returns a string representation of the minefield."""
        return linesep.join(self._lines)

    def __iter__(self) -> Iterator[PositionedCell]:
        for pos_y, row in enumerate(self._grid):
            for pos_x, cell in enumerate(row):
                yield PositionedCell(Vector2D(pos_x, pos_y), cell)

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
    def width(self) -> int:
        """Returns the width of the field."""
        return len(self._grid[0])

    @property
    def height(self) -> int:
        """Returns the height of the field."""
        return len(self._grid)

    @property
    def _header(self) -> Iterator[str]:
        """Returns the table header."""
        row = ' '.join(NUM_TO_STR[index] for index in range(self.width))
        yield f' |{row}| '
        yield '-+' + '-' * (self.width * 2 - 1) + '+-'

    @property
    def _lines(self) -> Iterator[str]:
        """Yield lines of the str representation."""
        yield from (header := list(self._header))

        for pos_y, row in enumerate(self._grid):
            prefix = NUM_TO_STR[pos_y]
            row = ' '.join(
                self._stringify(cell, pos_x, pos_y)
                for pos_x, cell in enumerate(row)
            )
            yield f'{prefix}|{row}|{prefix}'

        yield from reversed(header)

    @property
    def _uninitialized(self) -> bool:
        """Checks whether all cells are uninitalized."""
        return all(cell.mine is None for _, cell in self)

    @property
    def _uninitialized_cells(self) -> list[Cell]:
        """Yields cells that have not been initialized."""
        return [cell for _, cell in self if cell.mine is None]

    def _neighbors(self, position: Vector2D) -> Iterator[Cell]:
        """Yield cells surrounding the given position."""
        for neighbor in position.neighbors:
            if (cell := self.get(neighbor)):
                yield cell

    def _unvisited_neighbors(self, position: Vector2D) \
            -> Iterator[tuple[Vector2D, Cell]]:
        """Yield coordinate / cells tuples of cells that are unvisited."""
        for neighbor in position.neighbors:
            if (cell := self.get(neighbor)) and not cell.visited:
                yield (neighbor, cell)

    def _surrounding_mines(self, position: Vector2D) -> int:
        """Return the amount of mines surrounding the given position."""
        return sum(cell.mine for cell in self._neighbors(position))

    def _stringify(self, cell: Cell, pos_x: int, pos_y: int) -> str:
        """Return a str representation of the cell at the given coordiate."""
        if not cell.mine and (cell.visited or self._game_over):
            if mines := self._surrounding_mines(Vector2D(pos_x, pos_y)):
                return str(mines)

        return cell.to_string(game_over=self._game_over)

    def _initialize(self, start: Vector2D) -> None:
        """Inistialize the mine field."""
        # Ensure that we do not step on a mine on our first visit.
        self[start].mine = False

        for cell in sample(self._uninitialized_cells, k=self._mines):
            cell.mine = True

        for cell in self._uninitialized_cells:
            cell.mine = False

    def _visit_cell(self, cell: Cell) -> None:
        """Visits the given cell."""
        if cell.visited or cell.marked:
            return

        cell.visited = True

        if cell.mine:
            self._game_over = GameOver.LOST
        elif all(cell.visited for _, cell in self if not cell.mine):
            self._game_over = GameOver.WON

    def _visit_neighbors(self, position: Vector2D) -> None:
        """Visits the neighbors of the given position."""
        unvisited = dict(self._unvisited_neighbors(position))

        while unvisited:
            position, cell = unvisited.popitem()
            self._visit_cell(cell)

            if self._surrounding_mines(position) == 0:
                unvisited.update(dict(self._unvisited_neighbors(position)))

    def get(self, position: Vector2D) -> Optional[Cell]:
        """Returns the cell at the given coordinate,
        if is on the minefield or else None.
        """
        return self._grid[position.y][position.x] if position in self else None

    def toggle_marker(self, position: Vector2D) -> None:
        """Toggels the marker on the given cell."""
        self[position].toggle_marker()

    def visit(self, position: Vector2D) -> None:
        """Visit the cell at the given position."""
        if self._uninitialized:
            self._initialize(position)

        self._visit_cell(self[position])

        if self._surrounding_mines(position) == 0:
            self._visit_neighbors(position)

        if self._game_over:
            raise self._game_over


class ActionType(Enum):
    """Game actions."""

    VISIT = 'visit'
    MARK = 'mark'


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
            raise ValueError('Must specify exactly one command.')

        if 'visit'.startswith(action := action.casefold()):
            return cls(ActionType.VISIT, position)

        if 'mark'.startswith(action):
            return cls(ActionType.MARK, position)

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

        try:
            return Action.from_string(text)
        except ValueError as error:
            print(error)


def get_args(description: str = __doc__) -> Namespace:
    """Parses the command line arguments."""

    parser = ArgumentParser(description=description)
    parser.add_argument('--width', type=int, metavar='x', default=8)
    parser.add_argument('--height', type=int, metavar='y', default=8)
    parser.add_argument('--mines', type=int, metavar='n', default=10)
    return parser.parse_args()


def play_round(minefield: Minefield) -> None:
    """Play a round."""

    print(minefield)
    action = read_action()

    if action.action == ActionType.MARK:
        minefield.toggle_marker(action.position)
    else:
        minefield.visit(action.position)


def main() -> int:
    """Test stuff."""

    args = get_args()

    try:
        minefield = Minefield(args.width, args.height, args.mines)
    except ValueError as error:
        print(error, file=stderr)
        return int(Returncode.INVALID_PARAMETER)

    while True:
        try:
            play_round(minefield)
        except IndexError:
            print('Vector2D must lie on the minefield.', file=stderr)
        except KeyboardInterrupt:
            print('\nAborted by user.')
            return int(Returncode.USER_ABORT)
        except GameOver as game_over:
            print(minefield)
            print(game_over)
            return int(game_over)


if __name__ == '__main__':
    exit(main())
