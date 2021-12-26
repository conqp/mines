#! /usr/bin/env python3
"""A mine sweeping game."""

from __future__ import annotations
from argparse import ArgumentParser, Namespace
from contextlib import suppress
from dataclasses import dataclass
from enum import Enum
from random import choice
from sys import stderr
from typing import NamedTuple, Optional, Union


class OffGrid(ValueError):
    """Indicates that the given coordinate is not on the grid."""


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
        if self.visited:
            if self.mine:
                return '☠'
                
            return ' '

        if self.marked:
            return '⚐'
        
        return '■'


class Minefield(list):

    def __init__(self, width: int = 10, height: int = 10):
        self.width = width
        self.height = height

        for _ in range(height):
            self.append([Field() for _ in range(width)])

    def __str__(self) -> str:
        return '\n'.join(
            ' '.join(
                self.stringify(field, Coordinate(x, y))
                for x, field in enumerate(row)
            ) for y, row in enumerate(self)
        )
        
    def __getitem__(self, item: Union[int, Coordinate]) -> Union[list, Field]:
        if isinstance(item, Coordinate):
            return self.field_at(item)

        return super().__getitem__(item)

    def get_neighbors(self, position: Coordinate) -> Iterator[Field]:
        """Yield fields surrounding the given position."""
        for neighbor in position.neighbors:
            with suppress(ValueError):
                yield self[neighbor]

    def count_surrounding_mines(self, position: Coordinate) -> int:
        """Return the amount of mines surrounding the given position."""
        return sum(field.mine for field in self.get_neighbors(position))

    def stringify(self, field: Field, position: Coordinate) -> str:
        """Return a str representation of the field at the given coordiate."""
        if field.visited and not field.mine:
            return str(self.count_surrounding_mines(position) or ' ')

        return str(field)

    def disable_mine(self, position: Coordinate) -> None:
        """Set the field at the given position to not have a mine."""
        self[position].mine = False

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
            
    def field_at(self, position: Coordinate) -> Field:
        """Returns the field at the given position."""
        if 0 <= position.x < self.width and 0 <= position.y < self.width:
            return self[position.y][position.x]

        raise OffGrid('Coordinate not on field.')

    def toggle_mark(self, position: Coordinate) -> None:
        """Toggels the marker on the given field."""
        field.marked = not (field := self[position]).marked

    def visit(self, position: Coordinate) -> None:
        """Visit the field at the given position."""
        if (field := self[position]).visited:
            return

        field.visited = True
        
        if field.mine:
            raise SteppedOnMine()

        if self.count_surrounding_mines(position) == 0:
            for neighbor in position.neighbors:
                with suppress(OffGrid):
                    self.visit(neighbor)

    def sweep_completed(self) -> bool:
        """Checks whether all fields have been visited."""
        return all(field.visited for row in self for field in row)


class ActionType(Enum):
    """Game actions."""

    VISIT = 'visit'
    MARK = 'mark'


class Action(NamedTuple):
    """An action on a coordinate."""

    action: ActionType
    position: Coordinate


def read_action(prompt: str = 'Enter action and coordinate: ') -> Action:
    """Reads an Action."""
    
    try:
        text = input(prompt)
    except EOFError:
        return read_action(prompt)

    try:
        action, pos_x, pos_y = text.split()
        action = ActionType(action)
        position = Coordinate(int(pos_x), int(pos_y))
    except ValueError:
        print('Please enter: (visit|mark) <int:x> <int:y>', file=stderr) 
        return read_action(prompt)
    
    return Action(action, position)


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
        print(minefield)

        try:
            action = read_action()
        except KeyboardInterrupt:
            print('\nAborted by user.')
            return 2

        if action.action == Action.VISIT:
            if first_visit:
                first_visit = False
                minefield.disable_mine(action.position)
                minefield.populate(args.mines)

            try:
                minefield.visit(action.position)
            except SteppedOnMine:
                print('Game over.')
                return 1
        else:
            minefield.toggle_mark(action.position)

    return 0


if __name__ == '__main__':
    main()
