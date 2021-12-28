#! /usr/bin/env python3
"""A mine sweeping game."""

from __future__ import annotations
from argparse import ArgumentParser, Namespace
from contextlib import suppress
from dataclasses import dataclass
from enum import Enum
from itertools import filterfalse
from os import linesep
from random import choice
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
    'NotOnField',
    'Cell',
    'Coordinate',
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


class GameOver(Exception):
    """Indicates that the game has ended."""

    def __init__(self, message: str, returncode: int):
        super().__init__(message)
        self.message = message
        self.returncode = returncode


class NotOnField(Exception):
    """Indicates that a given coodinate does not lie on the minefield."""


@dataclass
class Cell:
    """A cell of a minefield."""

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

    def toggle_marked(self) -> None:
        """Toggles the marker on this field."""
        if self.visited:
            return

        self.marked = not self.marked


class Coordinate(NamedTuple):
    """A 2D coordinate on a grid."""

    x: int
    y: int

    @classmethod
    def from_strings(cls, strings: Iterator[str]) -> Coordinate:
        """Creates a coordinate from a set of strings."""
        try:
            return cls(*map(lambda pos: STR_TO_NUM[pos], strings))
        except KeyError as error:
            raise ValueError(f'Invalid coordinate value: {error}') from None
        except TypeError:
            raise ValueError('Expect two coordinates: x and y') from None

    @property
    def neighbors(self) -> Iterator[Coordinate]:
        """Yield fields surrounding this position."""
        for delta_y in range(-1, 2):
            for delta_x in range(-1, 2):
                if delta_x == delta_y == 0:
                    continue    # Skip the current position itself.

                yield type(self)(self.x + delta_x, self.y + delta_y)


class Minefield:
    """A mine field."""

    def __init__(self, width: int, height: int, mines: int):
        super().__init__()

        if width > (maxsize := len(NUM_TO_STR)) or height > maxsize:
            raise ValueError(f'Max field width and height are {maxsize}.')

        if mines >= (width * height - 1):
            raise ValueError('Too many mines for mine field.')

        self.width = width
        self.height = height
        self.mines = mines
        self.grid = [[Cell() for _ in range(width)] for _ in range(height)]
        self.game_over = None

    def __str__(self) -> str:
        """Returns a string representation of the minefield."""
        return linesep.join(self.lines)

    def __iter__(self) -> str:
        return (cell for row in self.grid for cell in row)

    def __contains__(self, item: Union[Cell, Coordinate]) -> bool:
        if isinstance(item, Cell):
            return any(cell is item for cell in self)

        if isinstance(self, Coordinate):
            return 0 <= item.x < self.width and 0 <= item.y < self.height

        return NotImplemented

    def __getitem__(self, position: Coordinate) -> Cell:
        """Returns the cell at the given position."""
        if not position in self:
            raise NotOnField(position)

        return self.grid[position.y][position.x]

    @property
    def header(self) -> Iterator[str]:
        """Returns the table header."""
        row = ' '.join(NUM_TO_STR[index] for index in range(self.width))
        yield f' |{row}'
        yield '-+' + '-' * (self.width * 2 - 1)

    @property
    def lines(self) -> Iterator[str]:
        """Yield lines of the str representation."""
        yield from self.header

        for pos_y, row in enumerate(self.grid):
            prefix = NUM_TO_STR[pos_y]
            row = ' '.join(
                self.stringify(cell, pos_x, pos_y)
                for pos_x, cell in enumerate(row)
            )
            yield f'{prefix}|{row}'

    @property
    def uninitialized(self) -> bool:
        """Checks whether all cells are uninitalized."""
        return all(cell.mine is None for cell in self)

    def get_neighbors(self, position: Coordinate) -> Iterator[Cell]:
        """Yield cells surrounding the given position."""
        for neighbor in position.neighbors:
            with suppress(NotOnField):
                yield self[neighbor]

    def count_surrounding_mines(self, position: Coordinate) -> int:
        """Return the amount of mines surrounding the given position."""
        return sum(cell.mine for cell in self.get_neighbors(position))

    def stringify(self, cell: Cell, pos_x: int, pos_y: int) -> str:
        """Return a str representation of the cell at the given coordiate."""
        if not cell.mine and (cell.visited or self.game_over):
            if mines := self.count_surrounding_mines(Coordinate(pos_x, pos_y)):
                return str(mines)

        return cell.to_string(game_over=self.game_over)

    def disable_mine(self, position: Coordinate) -> None:
        """Set the cell at the given position to not have a mine."""
        self[position].mine = False

    def populate(self) -> None:
        """Populate the minefield with mines."""
        cells = [cell for cell in self if cell.mine is None]

        for _ in range(self.mines):
            cell = choice(cells)
            cell.mine = True
            cells.remove(cell)

        for cell in cells:
            cell.mine = False

    def initialize(self, start: Coordinate) -> None:
        """Inistialize the mine field."""
        self.disable_mine(start)
        self.populate()

    def toggle_marked(self, position: Coordinate) -> None:
        """Toggels the marker on the given cell."""
        self[position].toggle_marked()

    def _visit(self, position: Coordinate) -> None:
        """Visits the respective position."""
        try:
            cell = self[position]
        except NotOnField:
            return

        if cell.visited or cell.marked:
            return

        cell.visited = True

        if cell.mine:
            self.game_over = GameOver('You stepped onto a mine. :(', 1)
        elif all(cell.visited for cell in self if not cell.mine):
            self.game_over = GameOver('All mines cleared. Great job.', 0)

        if self.count_surrounding_mines(position) == 0:
            for neighbor in position.neighbors:
                self._visit(neighbor)

    def visit(self, position: Coordinate) -> None:
        """Visit the cell at the given position."""
        if self.game_over:
            raise self.game_over

        if self.uninitialized:
            self.initialize(position)

        self._visit(position)

        if self.game_over:
            raise self.game_over


class ActionType(Enum):
    """Game actions."""

    VISIT = 'visit'
    MARK = 'mark'


class Action(NamedTuple):
    """An action on a coordinate."""

    action: ActionType
    position: Coordinate

    @classmethod
    def from_items(cls, items: list[str]) -> Action:
        """Creates an action from a list of strings."""
        position = Coordinate.from_strings(filter(str.isdigit, items))

        try:
            action, *excess = filterfalse(str.isdigit, items)
        except ValueError:
            return cls(ActionType.VISIT, position)

        if excess:
            raise ValueError('Must specify exactly one command.')

        if 'mark'.startswith(action := action.casefold()):
            return cls(ActionType.MARK, position)

        if 'visit'.startswith(action):
            return cls(ActionType.VISIT, position)

        raise ValueError(f'Action not recognized: {action}')

    @classmethod
    def from_string(cls, text: str) -> Action:
        """Parses an action from a string."""
        return cls.from_items(text.strip().split())


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
            continue


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
        minefield.toggle_marked(action.position)
    else:
        minefield.visit(action.position)


def main() -> int:
    """Test stuff."""

    args = get_args()

    try:
        minefield = Minefield(args.width, args.height, args.mines)
    except ValueError as error:
        print(error, file=stderr)
        return 2

    while True:
        try:
            play_round(minefield)
        except NotOnField as err:
            print(f'Coordinate must lie on the minefield: {err}', file=stderr)
        except KeyboardInterrupt:
            print('\nAborted by user.')
            return 3
        except GameOver as game_over:
            print(minefield)
            print(game_over.message)
            return game_over.returncode


if __name__ == '__main__':
    exit(main())
