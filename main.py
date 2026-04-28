"""
Morphlings Arena — entry point.

Owns nothing but the top-level mode switch (creator ↔ arena). Subsystems
manage their own state and entities; main.py destroys one and constructs the
other on transition.
"""
from ursina import Ursina, window

from config import WINDOW_BG
from creature_data import CreatureData

# Importing parts.py registers all built-in part types via decorators.
import parts  # noqa: F401

import sculptor as scl
import arena as ar


app = Ursina(title='Morphlings Arena', borderless=False)
window.color = WINDOW_BG


class Game:
    def __init__(self):
        self.cd       = CreatureData.load()
        self.mode     = None
        self.sculptor = None
        self.arena    = None

    def show_creator(self):
        self.mode = 'creator'
        if self.arena:
            self.arena.destroy_all()
            self.arena = None
        if self.sculptor:
            self.sculptor.destroy_all()
        self.sculptor = scl.Sculptor(self.cd, on_fight=self.start_arena)

    def start_arena(self):
        self.mode = 'arena'
        if self.sculptor:
            self.sculptor.destroy_all()
            self.sculptor = None
        if self.arena:
            self.arena.destroy_all()
        self.arena = ar.Arena(self.cd, on_back=self.show_creator)


GAME = Game()


def input(key):
    if GAME.mode == 'creator' and GAME.sculptor:
        GAME.sculptor.on_input(key)
    elif GAME.mode == 'arena' and GAME.arena:
        GAME.arena.on_input(key)


def update():
    if GAME.mode == 'creator' and GAME.sculptor:
        GAME.sculptor.on_update()
    elif GAME.mode == 'arena' and GAME.arena:
        GAME.arena.on_update()


GAME.show_creator()
app.run()
