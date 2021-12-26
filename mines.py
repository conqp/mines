#! /usr/bin/env python3
"""A mine sweeping game."""

from __future__ import annotations
from argparse import ArgumentParser, Namespace
from dataclasses import dataclass
from enum import Enum
from os import linesep
from random import choice
from sys import exit, stderr    # pylint: disable=W0622
from typing import Iterator, NamedTuple, Optional


class SteppedOnMine(Exception):
    """Indicates that the player stepped onto a mine."""


class Coordinate(NamedTuple):
    """A 2D coordinate on a grid."""

    x: int
    y: int

    def offset(self, delta_x: int, delta_y: int) -> Coordinate:
        """Returns a coordinate with the given offset."""
        return type(self)(self.x + delta_x, self.y + delta_y)

    @property
    def neighbors(self) -> Iterator[Coordinate]:
        """Yield fields surrounding this position."""
        for delta_y in range(-1, 2):
            for delta_x in range(-1, 2):
                if delta_x == delta_y == 0:
                    continue    # Skip the current position itself.

                yield self.offset(delta_x, delta_y)


@dataclass
class Field:
    """A field of a minefield."""

    mine: Optional[bool] = None
    marked: bool = False
    visited: bool = False

    def __str__(self) -> str:
        return self.to_string()

    def to_string(self, *, game_over: bool = False) -> str:
        """Returns a string representation."""
        if self.visited:
            if self.mine:
                return '*'

            return ' '

        if self.marked:
            if game_over:
                return '!' if self.mine else 'x'

            return '?'

        if game_over and self.mine:
            return 'o'

        return '■'

    def toggle_marked(self) -> None:
        """Toggles the marker on this field."""
        self.marked = not self.marked


class Minefield(list):
    """A mine field."""

    def __init__(self, width: int, height: int):
        super().__init__()
        self.width = width
        self.height = height

        for _ in range(height):
            self.append([Field() for _ in range(width)])

    def __str__(self) -> str:
        return self.to_string()

    def is_on_field(self, position: Coordinate) -> bool:
        """Determine whether the position is on the field."""
        return 0 <= position.x < self.width and 0 <= position.y < self.width

    def field_at(self, position: Coordinate) -> Field:
        """Returns the field at the given position."""
        return self[position.y][position.x]

    def get_neighbors(self, position: Coordinate) -> Iterator[Field]:
        """Yield fields surrounding the given position."""
        for neighbor in position.neighbors:
            if self.is_on_field(neighbor):
                yield self.field_at(neighbor)

    def count_surrounding_mines(self, position: Coordinate) -> int:
        """Return the amount of mines surrounding the given position."""
        return sum(field.mine for field in self.get_neighbors(position))

    def stringify(self, field: Field, position: Coordinate, *,
                  game_over: bool = False) -> str:
        """Return a str representation of the field at the given coordiate."""
        if field.visited and not field.mine:
            return str(self.count_surrounding_mines(position) or ' ')

        return str(field.to_string(game_over=game_over))

    def disable_mine(self, position: Coordinate) -> None:
        """Set the field at the given position to not have a mine."""
        self.field_at(position).mine = False

    def populate(self, mines: int) -> None:
        """Populate the mine field with mines."""
        fields = [field for row in self for field in row if field.mine is None]

        if mines > len(fields):
            raise ValueError('Too many mines for field.')

        for _ in range(mines):
            field = choice(fields)
            field.mine = True
            fields.remove(field)

        for field in fields:
            field.mine = False

    def toggle_marked(self, position: Coordinate) -> None:
        """Toggels the marker on the given field."""
        self.field_at(position).toggle_marked()

    def visit(self, position: Coordinate) -> None:
        """Visit the field at the given position."""
        if (field := self.field_at(position)).visited:
            return

        field.visited = True

        if field.mine:
            raise SteppedOnMine()

        if self.count_surrounding_mines(position) == 0:
            for neighbor in self.get_neighbors(position):
                self.visit(neighbor)

    def sweep_completed(self) -> bool:
        """Checks whether all fields have been visited."""
        return all(field.visited for row in self for field in row
                   if not field.mine)

    def to_string(self, *, game_over: bool = False) -> str:
        """Returns a string representation of the minefield."""
        return linesep.join(
            ' '.join(
                self.stringify(field, Coordinate(x, y), game_over=game_over)
                for x, field in enumerate(row)
            ) for y, row in enumerate(self)
        )


class ActionType(Enum):
    """Game actions."""

    VISIT = 'visit'
    MARK = 'mark'


class Action(NamedTuple):
    """An action on a coordinate."""

    action: ActionType
    position: Coordinate


def print_minefield(minefield: Minefield, *, game_over: bool = False) -> None:
    """Prints the mine field with row and column markers."""

    print(' |', *(f'{hex(index)[2]} ' for index in range(minefield.width)),
          sep='')
    print('-+', '-' * (minefield.width * 2 - 1), sep='')
    lines = minefield.to_string(game_over=game_over).split(linesep)

    for index, line in enumerate(lines):
        print(f'{hex(index)[2]}|', line, sep='')


def read_action(minefield: Minefield, *,
                prompt: str = 'Enter action and coordinate: '
                ) -> Action:
    """Reads an Action."""

    try:
        text = input(prompt)
    except EOFError:
        return read_action(minefield, prompt=prompt)

    try:
        action, pos_x, pos_y = text.split()
        action = ActionType(action)
        position = Coordinate(int(pos_x, 16), int(pos_y, 16))
    except ValueError:
        print('Please enter: (visit|mark) <int:x> <int:y>', file=stderr)
        return read_action(minefield, prompt=prompt)

    if minefield.is_on_field(position):
        return Action(action, position)

    print('Coordinate must lie on the minefield.', file=stderr)
    return read_action(minefield, prompt=prompt)


def get_args(description: str = __doc__) -> Namespace:
    """Parses the command line arguments."""

    parser = ArgumentParser(description=description)
    parser.add_argument('--width', type=int, default=8)
    parser.add_argument('--height', type=int, default=8)
    parser.add_argument('--mines', type=int, metavar='n', default=10)
    return parser.parse_args()


def main() -> int:
    """Test stuff."""

    args = get_args()
    minefield = Minefield(args.width, args.height)
    first_visit = True

    while not minefield.sweep_completed():
        print_minefield(minefield)

        try:
            action = read_action(minefield)
        except KeyboardInterrupt:
            print('\nAborted by user.')
            return 2

        if action.action == ActionType.VISIT:
            if first_visit:
                first_visit = False
                minefield.disable_mine(action.position)
                minefield.populate(args.mines)

            try:
                minefield.visit(action.position)
            except SteppedOnMine:
                print_minefield(minefield, game_over=True)
                print('Game over.')
                return 1
        else:
            minefield.toggle_marked(action.position)

    print_minefield(minefield, game_over=True)
    print('All mines cleared. Great job.')
    return 0


if __name__ == '__main__':
    exit(main())
