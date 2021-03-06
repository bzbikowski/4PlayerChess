#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This file is part of the Four-Player Chess project, a four-player chess GUI.
#
# Copyright (C) 2018, GammaDeltaII
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from PyQt5.QtCore import QObject, pyqtSignal, QSettings
from gui.settings import Settings
# Load settings
COM = '4pc'
APP = '4PlayerChess'
SETTINGS = Settings()

RED, BLUE, YELLOW, GREEN, PAWN, KNIGHT, BISHOP, ROOK, QUEEN, KING = range(10)

QUEENSIDE, KINGSIDE = (0, 1)

notLeftFile = 0xfffefffefffefffefffefffefffefffefffefffefffefffefffefffefffefffe
notRightFile = 0x7fff7fff7fff7fff7fff7fff7fff7fff7fff7fff7fff7fff7fff7fff7fff7fff
notTopRank = 0x0000ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff

boardMask = 0xff00ff00ff07ffe7ffe7ffe7ffe7ffe7ffe7ffe7ffe0ff00ff00ff00000  # without 3x3 corners
boardEdgeMask = 0xff008100810781e400240024002400240024002781e081008100ff00000
squareBoardMask = 0x7ffe7ffe7ffe7ffe7ffe7ffe7ffe7ffe7ffe7ffe7ffe7ffe7ffe7ffe0000  # full 14x14 board
squareBoardEdgeMask = 0x7ffe4002400240024002400240024002400240024002400240027ffe0000

# 256-bit De Bruijn sequence and corresponding index lookup
debruijn256 = 0x818283848586878898a8b8c8d8e8f929395969799a9b9d9e9faaeb6bedeeff
index256 = [0] * 256
for bit in range(256):
    index256[(((1 << bit) * debruijn256) >> 248) & 255] = bit


class Board(QObject):
    """The Board is the actual chess board and is the data structure shared between the View and the Algorithm."""
    boardReset = pyqtSignal()
    dataChanged = pyqtSignal(int, int)
    autoRotate = pyqtSignal(int)

    def __init__(self, files, ranks):
        super().__init__()
        self.files = files
        self.ranks = ranks
        self.boardData = []
        self.pieceBB = []
        self.emptyBB = 0
        self.occupiedBB = 0
        self.castlingState = []
        self.castlingSquares = []
        self.rooksSquares = []
        self.canPreventCheckmate = [False]*4
        self.initBoard()

    def pieceSet(self, color, piece):
        """Gets set of pieces of one type and color."""
        return self.pieceBB[color] & self.pieceBB[piece]

    def square(self, file, rank):
        """Little-Endian Rank-File (LERF) mapping for 14x14 bitboard embedded in 16x16 bitboard (to fit 256 bits)."""
        return (rank + 1) << 4 | (file + 1)

    def square256(self, file, rank):
        """Little-Endian Rank-File (LERF) mapping for 16x16 bitboard."""
        return rank << 4 | file

    def fileRank(self, square):
        """Returns file and rank of square."""
        return (square & 15) - 1, (square >> 4) - 1

    def bitScanForward(self, bitboard):
        """Finds the index of the least significant 1 bit (LS1B) using De Bruijn sequence multiplication."""
        assert bitboard != 0
        return index256[(((bitboard & -bitboard) * debruijn256) >> 248) & 255]

    def getSquares(self, bitboard):
        """Returns list of squares (file, rank) corresponding to ones in bitboard."""
        squares = []
        while bitboard != 0:
            square = self.bitScanForward(bitboard)
            squares.append(self.fileRank(square))
            bitboard ^= 1 << square
        return squares

    # def flipVertical(self, bitboard):
    #     """Flips bitboard vertically (parallel prefix approach, 4 delta swaps)."""
    #     k1 = 0x0000ffff0000ffff0000ffff0000ffff0000ffff0000ffff0000ffff0000ffff
    #     k2 = 0x00000000ffffffff00000000ffffffff00000000ffffffff00000000ffffffff
    #     k3 = 0x0000000000000000ffffffffffffffff0000000000000000ffffffffffffffff
    #     bitboard = ((bitboard >> 16) & k1) | ((bitboard & k1) << 16)
    #     bitboard = ((bitboard >> 32) & k2) | ((bitboard & k2) << 32)
    #     bitboard = ((bitboard >> 64) & k3) | ((bitboard & k3) << 64)
    #     bitboard = (bitboard >> 128) | (bitboard << 128)
    #     return bitboard

    # def flipHorizontal(self, bitboard):
    #     """Flips bitboard horizontally (parallel prefix approach, 4 delta swaps)."""
    #     k1 = 0x5555555555555555555555555555555555555555555555555555555555555555
    #     k2 = 0x3333333333333333333333333333333333333333333333333333333333333333
    #     k3 = 0x0f0f0f0f0f0f0f0f0f0f0f0f0f0f0f0f0f0f0f0f0f0f0f0f0f0f0f0f0f0f0f0f
    #     k4 = 0x00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff
    #     bitboard = ((bitboard >> 1) & k1) | ((bitboard & k1) << 1)
    #     bitboard = ((bitboard >> 2) & k2) | ((bitboard & k2) << 2)
    #     bitboard = ((bitboard >> 4) & k3) | ((bitboard & k3) << 4)
    #     bitboard = ((bitboard >> 8) & k4) | ((bitboard & k4) << 8)
    #     return bitboard

    # def flipDiagonal(self, bitboard):
    #     """Flips bitboard about diagonal from lower left to upper right (parallel prefix approach, 4 delta swaps)."""
    #     k1 = 0x5555000055550000555500005555000055550000555500005555000055550000
    #     k2 = 0x3333333300000000333333330000000033333333000000003333333300000000
    #     k3 = 0x0f0f0f0f0f0f0f0f00000000000000000f0f0f0f0f0f0f0f0000000000000000
    #     k4 = 0x00ff00ff00ff00ff00ff00ff00ff00ff00000000000000000000000000000000
    #     t = k4 & (bitboard ^ (bitboard << 120))
    #     bitboard ^= t ^ (t >> 120)
    #     t = k3 & (bitboard ^ (bitboard << 60))
    #     bitboard ^= t ^ (t >> 60)
    #     t = k2 & (bitboard ^ (bitboard << 30))
    #     bitboard ^= t ^ (t >> 30)
    #     t = k1 & (bitboard ^ (bitboard << 15))
    #     bitboard ^= t ^ (t >> 15)
    #     return bitboard

    # def flipAntiDiagonal(self, bitboard):
    #     """Flips bitboard about diagonal from upper left to lower right (parallel prefix approach, 4 delta swaps)."""
    #     k1 = 0xaaaa0000aaaa0000aaaa0000aaaa0000aaaa0000aaaa0000aaaa0000aaaa0000
    #     k2 = 0xcccccccc00000000cccccccc00000000cccccccc00000000cccccccc00000000
    #     k3 = 0xf0f0f0f0f0f0f0f00000000000000000f0f0f0f0f0f0f0f00000000000000000
    #     k4 = 0xff00ff00ff00ff00ff00ff00ff00ff0000ff00ff00ff00ff00ff00ff00ff00ff
    #     t = bitboard ^ (bitboard << 136)
    #     bitboard ^= k4 & (t ^ (bitboard >> 136))
    #     t = k3 & (bitboard ^ (bitboard << 68))
    #     bitboard ^= t ^ (t >> 68)
    #     t = k2 & (bitboard ^ (bitboard << 34))
    #     bitboard ^= t ^ (t >> 34)
    #     t = k1 & (bitboard ^ (bitboard << 17))
    #     bitboard ^= t ^ (t >> 17)
    #     return bitboard

    # def rotate(self, bitboard, degrees):
    #     """Rotates bitboard +90 (clockwise), -90 (counterclockwise) or 180 degrees using two flips."""
    #     if degrees == 90:
    #         return self.flipVertical(self.flipDiagonal(bitboard))
    #     elif degrees == -90:
    #         return self.flipVertical(self.flipAntiDiagonal(bitboard))
    #     elif degrees == 180:
    #         return self.flipHorizontal(self.flipVertical(bitboard))
    #     else:
    #         pass

    def shiftN(self, bitboard, n=1):
        """Shifts bitboard north by n squares."""
        for _ in range(n):
            bitboard = (bitboard << 16) & notTopRank
        return bitboard

    def shiftNE(self, bitboard, n=1):
        """Shifts bitboard north-east by n squares."""
        for _ in range(n):
            bitboard = (bitboard << 17) & notLeftFile
        return bitboard

    def shiftE(self, bitboard, n=1):
        """Shifts bitboard east by n squares."""
        for _ in range(n):
            bitboard = (bitboard << 1) & notLeftFile
        return bitboard

    def shiftSE(self, bitboard, n=1):
        """Shifts bitboard south-east by n squares."""
        for _ in range(n):
            bitboard = (bitboard >> 15) & notRightFile
        return bitboard

    def shiftS(self, bitboard, n=1):
        """Shifts bitboard south by n squares."""
        for _ in range(n):
            bitboard >>= 16  # no wrap mask needed, as bits just fall off
        return bitboard

    def shiftSW(self, bitboard, n=1):
        """Shifts bitboard south-west by n squares."""
        for _ in range(n):
            bitboard = (bitboard >> 17) & notRightFile
        return bitboard

    def shiftW(self, bitboard, n=1):
        """Shifts bitboard west by n squares."""
        for _ in range(n):
            bitboard = (bitboard >> 1) & notRightFile
        return bitboard

    def shiftNW(self, bitboard, n=1):
        """Shifts bitboard north-west by n squares."""
        for _ in range(n):
            bitboard = (bitboard << 15) & notLeftFile
        return bitboard

    def rankMask(self, origin):
        """Returns rank passing through origin, excluding origin itself."""
        return (0xffff << (origin & 240)) ^ (1 << origin)  # excluding piece square

    def fileMask(self, origin):
        """Returns file passing through origin, excluding origin itself."""
        return (0x1000100010001000100010001000100010001000100010001000100010001 << (origin & 15)) ^ (1 << origin)

    def diagonalMask(self, origin):
        """Returns diagonal passing through origin, excluding origin itself."""
        mainDiagonal = 0x8000400020001000080004000200010000800040002000100008000400020001
        diagonal = 16 * (origin & 15) - (origin & 240)
        north = -diagonal & (diagonal >> 63)
        south = diagonal & (-diagonal >> 63)
        return ((mainDiagonal >> south) << north) ^ (1 << origin)

    def antiDiagonalMask(self, origin):
        """Returns anti-diagonal passing through origin, excluding origin itself."""
        mainDiagonal = 0x1000200040008001000200040008001000200040008001000200040008000
        diagonal = 240 - 16 * (origin & 15) - (origin & 240)
        north = -diagonal & (diagonal >> 63)
        south = diagonal & (-diagonal >> 63)
        return ((mainDiagonal >> south) << north) ^ (1 << origin)

    def rayBeyond(self, origin, square):
        """Returns part of ray from origin beyond blocker square."""
        sign = lambda x: (1, -1)[x < 0]
        diff = square - origin
        s = sign(diff)
        direction = max([d if not diff % d else 1 for d in (15, 16, 17)])
        positive = -2 << square
        negative = (1 << square) - 1
        if direction == 1:
            return self.rankMask(square) & (positive if s > 0 else negative)
        elif direction == 15:
            return self.antiDiagonalMask(square) & (positive if s > 0 else negative)
        elif direction == 16:
            return self.fileMask(square) & (positive if s > 0 else negative)
        elif direction == 17:
            return self.diagonalMask(square) & (positive if s > 0 else negative)
        else:
            return 0

    def rayBetween(self, origin, square):
        """Returns part of ray from origin to square."""
        sign = lambda x: (1, -1)[x < 0]
        diff = square - origin
        s = sign(diff)
        direction = max([d if not diff % d else 1 for d in (15, 16, 17)])
        posSquare = -2 << square
        negSquare = (1 << square) - 1
        posOrigin = -2 << origin
        negOrigin = (1 << origin) - 1
        if direction == 1:
            return (self.rankMask(square) & (negSquare if s > 0 else posSquare)) & \
                   (self.rankMask(origin) & (posOrigin if s > 0 else negOrigin))
        elif direction == 15:
            return (self.antiDiagonalMask(square) & (negSquare if s > 0 else posSquare)) & \
                   (self.antiDiagonalMask(origin) & (posOrigin if s > 0 else negOrigin))
        elif direction == 16:
            return (self.fileMask(square) & (negSquare if s > 0 else posSquare)) & \
                   (self.fileMask(origin) & (posOrigin if s > 0 else negOrigin))
        elif direction == 17:
            return (self.diagonalMask(square) & (negSquare if s > 0 else posSquare)) & \
                   (self.diagonalMask(origin) & (posOrigin if s > 0 else negOrigin))
        else:
            return 0

    def maskBlockedSquares(self, moves, origin, occupied=None):
        """Masks blocked parts of sliding piece attack sets."""
        if not occupied:
            occupied = self.occupiedBB
        blockers = moves & occupied
        while blockers != 0:
            blockerSquare = self.bitScanForward(blockers)
            moves &= ~self.rayBeyond(origin, blockerSquare)
            blockers &= blockers - 1
        return moves

    def showAvailableCastlingMoves(self, moves, origin, color):
        """Return available castling moves for king of given color."""
        # if king in check, cannot castle
        if moves == 0:
            return 0
        sides = [KINGSIDE, QUEENSIDE]
        # check if castle was already done
        if color in [RED, YELLOW]:
            opp = [GREEN, BLUE]
        elif color in [GREEN, BLUE]:
            opp = [RED, YELLOW]
        else:
            return
        teammate_color = color + 2
        if teammate_color >= 4:
            teammate_color -= 4
        final_mask = 0
        for side in sides:
            # check if castle available for this side
            if moves[side] < 1:
                continue
            # check if any ally pieces stand between king and rook
            rookSquare = self.bitScanForward(self.rooksSquares[color][side])
            if self.rayBetween(origin, rookSquare) & (self.pieceBB[color] | self.pieceBB[teammate_color]):
                continue
            # check if castling square and square between king and this square are under attack

            targetSquare = self.bitScanForward(self.castlingSquares[color][side])
            broken = False
            for square in self.getSquares(self.rayBetween(origin, targetSquare) | (1 << targetSquare)):
                square = self.square(square[0], square[1])
                if self.attacked(square, opp[0]) or self.attacked(square, opp[1]):
                    broken = True
                    break
            if broken:
                continue
            # if not, add castling by moving into rook square or castling square
            final_mask |= (self.castlingSquares[color][side] | self.rooksSquares[color][side])
        return final_mask

    def legalMoves(self, piece, origin, color):
        """Return all legal moves for piece type."""
        if color in (RED, YELLOW):
            friendly = self.pieceBB[RED] | self.pieceBB[YELLOW]
        else:
            friendly = self.pieceBB[BLUE] | self.pieceBB[GREEN]

        if (1 << origin) & self.absolutePins(color):
            pinMask = self.kingRay(origin, color)
        else:
            pinMask = -1
        # if (1 << origin) & self.absolutePinsTeammate(color):
        #     pinMaskTeammate = self.kingRayTeammate(origin, color)
        # else:
        #     pinMaskTeammate = -1
        # pinMask &= pinMaskTeammate
        if piece == PAWN:
            legal_moves = self.pawnMoves(origin, color) & ~friendly & pinMask
        elif piece == KNIGHT:
            legal_moves = self.knightMoves(origin) & ~friendly & pinMask
        elif piece == BISHOP:
            legal_moves = self.maskBlockedSquares(self.bishopMoves(origin), origin) & ~friendly & pinMask
        elif piece == ROOK:
            legal_moves = self.maskBlockedSquares(self.rookMoves(origin), origin) & ~friendly & pinMask
        elif piece == QUEEN:
            legal_moves = self.maskBlockedSquares(self.queenMoves(origin), origin) & ~friendly & pinMask
        elif piece == KING:
            if self.kingInCheck(color)[0]:
                castlingMoves = 0
            else:
                castlingMoves = self.castlingState[color]
            # rookSquares = self.rooksSquares[color]
            legal_moves = self.kingMoves(origin) & ~friendly
            if color in [RED, YELLOW]:
                opp = [GREEN, BLUE]
            elif color in [GREEN, BLUE]:
                opp = [RED, YELLOW]
            else:
                return
            operations = {0: self.shiftSW,
                          1: self.shiftS,
                          2: self.shiftSE,
                          3: self.shiftW,
                          4: self.shiftE,
                          5: self.shiftNW,
                          6: self.shiftN,
                          7: self.shiftNE}
            # check if new positions are not under another check
            possible = 0
            # delete king from board temporary
            origin_map = (1 << origin)
            self.occupiedBB &= ~origin_map
            for i in range(8):
                new_position = operations[i](origin_map)
                if boardMask & new_position == 0:
                    continue
                new_position_square = self.bitScanForward(new_position)
                if self.attacked(new_position_square, opp[0]) or self.attacked(new_position_square, opp[1]):
                    continue
                possible |= new_position
            # restore king
            self.occupiedBB |= origin_map

            legal_moves &= possible
            # all legal moves without castling
            # legal_moves |= self.showAvailableCastlingMoves(castlingMoves, origin, color, rookSquares)
            legal_moves |= self.showAvailableCastlingMoves(castlingMoves, origin, color)
        else:
            return -1
        # find king on chessboard on correct color
        check, position = self.kingInCheck(color)
        king_square = self.square(position[0], position[1])
        # must prevent checkmate
        if check:
            # return only moves that prevent checkmate
            # first -> takeout attacking piece
            # * search for pieces attacking king
            if color in [RED, YELLOW]:
                opp = [GREEN, BLUE]
            elif color in [GREEN, BLUE]:
                opp = [RED, YELLOW]
            else:
                return
            position_of_attacking_pieces = self.attackers(king_square, opp[0]) | self.attackers(king_square, opp[1])
            # * compare their position with possible moves
            first_option = legal_moves & position_of_attacking_pieces
            if piece == KING:
                # second -> move with king
                # check if new positions are not under another check
                return legal_moves
            else:
                # third -> block attacking piece
                # * search for pieces attacking king
                attacking_pieces = self.getSquares(position_of_attacking_pieces)
                if len(attacking_pieces) >= 2:
                    # you must move the king, can't capture or block two pieces at once
                    return 0
                all_possible_moves = 0
                for piece in attacking_pieces:
                    piece_square = self.square(piece[0], piece[1])
                    ray = self.rayBetween(king_square, piece_square)
                    if all_possible_moves == 0:
                        all_possible_moves = ray
                    else:
                        all_possible_moves &= ray
                # * get all attacking squares
                # * compare with all possible moves
                second_option = legal_moves & all_possible_moves
                return first_option | second_option

        # teammate_color = color + 2
        # if teammate_color >= 4:
        #     teammate_color -= 4
        # # check if you can prevent teammate from getting checkmated
        # if self.canPreventCheckmate[teammate_color]:
        #     if color in [RED, YELLOW]:
        #         opp = [GREEN, BLUE]
        #     elif color in [GREEN, BLUE]:
        #         opp = [RED, YELLOW]
        #     else:
        #         return
        #
        #     operations = {0: self.shiftSW,
        #                   1: self.shiftS,
        #                   2: self.shiftSE,
        #                   3: self.shiftW,
        #                   4: self.shiftE,
        #                   5: self.shiftNW,
        #                   6: self.shiftN,
        #                   7: self.shiftNE}
        #     origin = self.pieceSet(teammate_color, KING)
        #     all_possible_moves = 0
        #     for i in range(8):
        #         new_position = operations[i](origin)
        #         if boardMask & new_position == 0:
        #             continue
        #         new_position_square = self.bitScanForward(new_position)
        #         # check if that position is empty
        #         if self.emptyBB & new_position != 0:
        #             # get all pieces, that attack this square
        #             attackers = self.attackers(new_position_square, opp[0]) | self.attackers(new_position_square,
        #                                                                                      opp[1])
        #             attackers_position = self.getSquares(attackers)
        #             # if more than 2 attackers, you can't block it
        #             if len(attackers_position) >= 2:
        #                 continue
        #             # check if you can block
        #             attacker_square = self.square(attackers_position[0][0], attackers_position[0][1])
        #             ray = self.rayBetween(new_position_square, attacker_square)
        #             if_can_block = legal_moves & ray
        #             if if_can_block != 0:
        #                 all_possible_moves |= if_can_block
        #
        #     king_square = self.bitScanForward(origin)
        #     position_of_attacking_pieces = self.attackers(king_square, opp[0]) | self.attackers(king_square, opp[1])
        #
        #     first_option = legal_moves & position_of_attacking_pieces
        #
        #     attacking_pieces = self.getSquares(position_of_attacking_pieces)
        #
        #     all_possible_moves2 = 0
        #     for off_piece in attacking_pieces:
        #         piece_square = self.square(off_piece[0], off_piece[1])
        #         ray = self.rayBetween(king_square, piece_square)
        #         if all_possible_moves2 == 0:
        #             all_possible_moves2 = ray
        #         else:
        #             all_possible_moves2 &= ray
        #
        #     second_option = legal_moves & all_possible_moves2
        #     return first_option | second_option | all_possible_moves

        return legal_moves

    # def checkIfTeammateCanPreventCheckmate(self, color):
    #     """Check if teammate of team color can prevent checkmate"""
    #     # get color of your teammate
    #     teammate_color = color + 2
    #     if teammate_color >= 4:
    #         teammate_color -= 4
    #
    #     if teammate_color in [RED, YELLOW]:
    #         opp = [GREEN, BLUE]
    #     elif teammate_color in [GREEN, BLUE]:
    #         opp = [RED, YELLOW]
    #     else:
    #         return
    #     # get position of king
    #     king_file, king_rank = self.getSquares(self.pieceSet(color, KING))[0]
    #     king_square = self.square(king_file, king_rank)
    #
    #     # get bitmap of pieces attacking the king
    #     position_of_attacking_pieces = self.attackers(king_square, opp[0]) | self.attackers(king_square, opp[1])
    #
    #     # check every type of piece that your teammate have
    #     for piece_type in [PAWN, KNIGHT, BISHOP, ROOK, QUEEN, KING]:
    #         for piece in self.getSquares(self.pieceSet(teammate_color, piece_type)):
    #             # get all legal moves for every piece of it's type
    #             square = self.square(piece[0], piece[1])
    #             legal_moves = self.legalMoves(piece, square, teammate_color)
    #
    #             # check if you can take attacking piece
    #             first_option = legal_moves & position_of_attacking_pieces
    #
    #             # get position of all the attacking pieces on king
    #             attacking_pieces = self.getSquares(position_of_attacking_pieces)
    #
    #             # get all field around king, that are empty
    #             # get ray of that field, check if you can block piece, that attack it
    #             if color in [RED, YELLOW]:
    #                 opp = [GREEN, BLUE]
    #             elif color in [GREEN, BLUE]:
    #                 opp = [RED, YELLOW]
    #             else:
    #                 return
    #             operations = {0: self.shiftSW,
    #                           1: self.shiftS,
    #                           2: self.shiftSE,
    #                           3: self.shiftW,
    #                           4: self.shiftE,
    #                           5: self.shiftNW,
    #                           6: self.shiftN,
    #                           7: self.shiftNE}
    #             origin = self.pieceSet(color, KING)
    #             for i in range(8):
    #                 new_position = operations[i](origin)
    #                 if boardMask & new_position == 0:
    #                     continue
    #                 new_position_square = self.bitScanForward(new_position)
    #                 # check if that position is empty
    #                 if self.emptyBB & new_position != 0:
    #                     # get all pieces, that attack this square
    #                     attackers = self.attackers(new_position_square, opp[0]) | self.attackers(new_position_square, opp[1])
    #                     attackers_position = self.getSquares(attackers)
    #                     # if more than 2 attackers, you can't block it
    #                     if len(attackers_position) >= 2:
    #                         continue
    #                     # check if you can block
    #                     attacker_square = self.square(attackers_position[0][0], attackers_position[0][1])
    #                     ray = self.rayBetween(new_position_square, attacker_square)
    #                     if_can_block = legal_moves & ray
    #                     if if_can_block != 0:
    #                         self.canPreventCheckmate[color] = True
    #                         return True
    #
    #             all_possible_moves = 0
    #             # check if u can block one of attacking pieces
    #             for off_piece in attacking_pieces:
    #                 piece_square = self.square(off_piece[0], off_piece[1])
    #                 ray = self.rayBetween(king_square, piece_square)
    #                 if all_possible_moves == 0:
    #                     all_possible_moves = ray
    #                 else:
    #                     all_possible_moves &= ray
    #             second_option = legal_moves & all_possible_moves
    #             if (first_option | second_option) != 0:
    #                 self._about_to_get_checkmated[color] = True
    #                 return True
    #     return False

    def attackers(self, square, color):
        """Returns the set of all pieces attacking the target square."""
        if color == RED:
            opposite = YELLOW
        elif color == YELLOW:
            opposite = RED
        elif color == BLUE:
            opposite = GREEN
        elif color == GREEN:
            opposite = BLUE
        else:
            return
        attackers = self.pawnMoves(square, opposite, True) & self.pieceSet(color, PAWN)
        attackers |= self.knightMoves(square) & self.pieceSet(color, KNIGHT)
        bishopMoves = self.maskBlockedSquares(self.bishopMoves(square), square)
        attackers |= bishopMoves & (self.pieceSet(color, BISHOP) | self.pieceSet(color, QUEEN))
        rookMoves = self.maskBlockedSquares(self.rookMoves(square), square)
        attackers |= rookMoves & (self.pieceSet(color, ROOK) | self.pieceSet(color, QUEEN))
        return attackers

    def defenders(self):
        """Returns the set of all pieces defending the target square."""
        defenders = 0
        # attackers = self.pawnMoves(square, RED, True) & self.pieceSet(YELLOW, PAWN)
        # attackers |= self.pawnMoves(square, YELLOW, True) & self.pieceSet(RED, PAWN)
        # attackers |= self.pawnMoves(square, BLUE, True) & self.pieceSet(GREEN, PAWN)
        # attackers |= self.pawnMoves(square, GREEN, True) & self.pieceSet(BLUE, PAWN)
        # attackers |= self.knightMoves(square) & self.pieceBB[KNIGHT]
        # attackers |= self.kingMoves(square) & self.pieceBB[KING]
        # bishopMoves = self.maskBlockedSquares(self.bishopMoves(square), square)
        # attackers |= bishopMoves & (self.pieceBB[BISHOP] | self.pieceBB[QUEEN])
        # rookMoves = self.maskBlockedSquares(self.rookMoves(square), square)
        # attackers |= rookMoves & (self.pieceBB[ROOK] | self.pieceBB[QUEEN])
        return defenders

    def pawnMoves(self, origin, color, attacksOnly=False):
        """Pseudo-legal pawn moves."""
        rank4 = 0x00000000000000000000000000000000000000000000ffff0000000000000000
        rank11 = 0x0000000000000000ffff00000000000000000000000000000000000000000000
        fileD = 0x0010001000100010001000100010001000100010001000100010001000100010
        fileK = 0x0800080008000800080008000800080008000800080008000800080008000800
        origin = 1 << origin
        if color == RED:
            singlePush = self.shiftN(origin) & self.emptyBB
            doublePush = self.shiftN(singlePush) & self.emptyBB & rank4
            attacks = self.shiftNW(origin) | self.shiftNE(origin)
            captures = attacks & (self.pieceBB[BLUE] | self.pieceBB[GREEN])
        elif color == BLUE:
            singlePush = self.shiftE(origin) & self.emptyBB
            doublePush = self.shiftE(singlePush) & self.emptyBB & fileD
            attacks = self.shiftNE(origin) | self.shiftSE(origin)
            captures = attacks & (self.pieceBB[RED] | self.pieceBB[YELLOW])
        elif color == YELLOW:
            singlePush = self.shiftS(origin) & self.emptyBB
            doublePush = self.shiftS(singlePush) & self.emptyBB & rank11
            attacks = self.shiftSE(origin) | self.shiftSW(origin)
            captures = attacks & (self.pieceBB[BLUE] | self.pieceBB[GREEN])
        elif color == GREEN:
            singlePush = self.shiftW(origin) & self.emptyBB
            doublePush = self.shiftW(singlePush) & self.emptyBB & fileK
            attacks = self.shiftSW(origin) | self.shiftNW(origin)
            captures = attacks & (self.pieceBB[RED] | self.pieceBB[YELLOW])
        else:
            return 0
        if attacksOnly:  # only return attacked squares
            return attacks & boardMask
        else:
            return (singlePush | doublePush | captures) & boardMask

    def knightMoves(self, origin):
        """Pseudo-legal knight moves."""
        origin = 1 << origin
        NNE = self.shiftN(self.shiftNE(origin))
        NEE = self.shiftNE(self.shiftE(origin))
        SEE = self.shiftSE(self.shiftE(origin))
        SSE = self.shiftS(self.shiftSE(origin))
        SSW = self.shiftS(self.shiftSW(origin))
        SWW = self.shiftSW(self.shiftW(origin))
        NWW = self.shiftNW(self.shiftW(origin))
        NNW = self.shiftN(self.shiftNW(origin))
        return (NNE | NEE | SEE | SSE | SSW | SWW | NWW | NNW) & boardMask

    def bishopMoves(self, origin):
        """Pseudo-legal bishop moves."""
        return (self.diagonalMask(origin) | self.antiDiagonalMask(origin)) & boardMask

    def rookMoves(self, origin):
        """Pseudo-legal rook moves."""
        return (self.fileMask(origin) | self.rankMask(origin)) & boardMask

    def queenMoves(self, origin):
        """Pseudo-legal queen moves (= union of bishop and rook)."""
        return (self.bishopMoves(origin) | self.rookMoves(origin)) & boardMask

    def kingMoves(self, origin):
        """Pseudo-legal king moves."""
        kingSet = 1 << origin
        moves = self.shiftW(kingSet) | self.shiftE(kingSet)
        kingSet |= moves
        moves |= self.shiftN(kingSet) | self.shiftS(kingSet)
        return moves & boardMask

    def xrayRookAttacks(self, blockers, origin):
        """Returns X-ray rook attacks through blockers."""
        attacks = self.maskBlockedSquares(self.rookMoves(origin), origin)
        blockers &= attacks
        return attacks ^ self.maskBlockedSquares(self.rookMoves(origin), origin, self.occupiedBB ^ blockers)

    def xrayBishopAttacks(self, blockers, origin):
        """Returns X-ray rook attacks through blockers."""
        attacks = self.maskBlockedSquares(self.bishopMoves(origin), origin)
        blockers &= attacks
        return attacks ^ self.maskBlockedSquares(self.bishopMoves(origin), origin, self.occupiedBB ^ blockers)

    def absolutePins(self, color):
        """Returns absolutely (partially) pinned pieces."""
        pinned = 0
        ownPieces = self.pieceBB[color]
        kingSquare = self.bitScanForward(self.pieceSet(color, KING))
        if color in (RED, YELLOW):
            opponentRQ = self.pieceSet(BLUE, ROOK) | self.pieceSet(BLUE, QUEEN) | \
                         self.pieceSet(GREEN, ROOK) | self.pieceSet(GREEN, QUEEN)
            opponentBQ = self.pieceSet(BLUE, BISHOP) | self.pieceSet(BLUE, QUEEN) | \
                         self.pieceSet(GREEN, BISHOP) | self.pieceSet(GREEN, QUEEN)
        else:
            opponentRQ = self.pieceSet(RED, ROOK) | self.pieceSet(RED, QUEEN) | \
                         self.pieceSet(YELLOW, ROOK) | self.pieceSet(YELLOW, QUEEN)
            opponentBQ = self.pieceSet(RED, BISHOP) | self.pieceSet(RED, QUEEN) | \
                         self.pieceSet(YELLOW, BISHOP) | self.pieceSet(YELLOW, QUEEN)
        pinner = self.xrayRookAttacks(ownPieces, kingSquare) & opponentRQ
        while pinner:
            square = self.bitScanForward(pinner)
            pinned |= self.rayBetween(square, kingSquare) & ownPieces
            pinner &= pinner - 1
        pinner = self.xrayBishopAttacks(ownPieces, kingSquare) & opponentBQ
        while pinner:
            square = self.bitScanForward(pinner)
            pinned |= self.rayBetween(square, kingSquare) & ownPieces
            pinner &= pinner - 1
        return pinned

    # def absolutePinsTeammate(self, color):
    #     """Returns absolutely (partially) pinned pieces."""
    #     teammate_color = color + 2
    #     if teammate_color >= 4:
    #         teammate_color -= 4
    #     pinned = 0
    #     ownPieces = self.pieceBB[color]
    #     kingSquare = self.bitScanForward(self.pieceSet(teammate_color, KING))
    #     if color in (RED, YELLOW):
    #         opponentRQ = self.pieceSet(BLUE, ROOK) | self.pieceSet(BLUE, QUEEN) | \
    #                      self.pieceSet(GREEN, ROOK) | self.pieceSet(GREEN, QUEEN)
    #         opponentBQ = self.pieceSet(BLUE, BISHOP) | self.pieceSet(BLUE, QUEEN) | \
    #                      self.pieceSet(GREEN, BISHOP) | self.pieceSet(GREEN, QUEEN)
    #     else:
    #         opponentRQ = self.pieceSet(RED, ROOK) | self.pieceSet(RED, QUEEN) | \
    #                      self.pieceSet(YELLOW, ROOK) | self.pieceSet(YELLOW, QUEEN)
    #         opponentBQ = self.pieceSet(RED, BISHOP) | self.pieceSet(RED, QUEEN) | \
    #                      self.pieceSet(YELLOW, BISHOP) | self.pieceSet(YELLOW, QUEEN)
    #     pinner = self.xrayRookAttacks(ownPieces, kingSquare) & opponentRQ
    #     while pinner:
    #         square = self.bitScanForward(pinner)
    #         pinned |= self.rayBetween(square, kingSquare) & ownPieces
    #         pinner &= pinner - 1
    #     pinner = self.xrayBishopAttacks(ownPieces, kingSquare) & opponentBQ
    #     while pinner:
    #         square = self.bitScanForward(pinner)
    #         pinned |= self.rayBetween(square, kingSquare) & ownPieces
    #         pinner &= pinner - 1
    #     return pinned

    # def aligned(self, origin, target, kingSquare):
    #     """Checks if partially pinned piece is moved along ray from or towards king."""
    #     alongRay = self.rayBetween(origin, kingSquare) & (1 << target)
    #     alongRay |= self.rayBetween(target, kingSquare) & (1 << origin)
    #     return alongRay

    def kingRay(self, square, color):
        """Returns ray from king that contains square."""
        kingSquare = self.bitScanForward(self.pieceSet(color, KING))
        return self.rayBetween(kingSquare, square) | self.rayBeyond(kingSquare, square)

    def kingRayTeammate(self, square, color):
        """Returns ray from king that contains square."""
        teammate_color = color + 2
        if teammate_color >= 4:
            teammate_color -= 4
        kingSquare = self.bitScanForward(self.pieceSet(teammate_color, KING))
        return self.rayBetween(kingSquare, square) | self.rayBeyond(kingSquare, square)

    def attacked(self, square, color):
        """Checks if a square is attacked by a player."""
        if color == RED:
            opposite = YELLOW
        elif color == YELLOW:
            opposite = RED
        elif color == BLUE:
            opposite = GREEN
        elif color == GREEN:
            opposite = BLUE
        else:
            return False
        if self.pawnMoves(square, opposite, True) & self.pieceSet(color, PAWN):
            return True
        if self.knightMoves(square) & self.pieceSet(color, KNIGHT):
            return True
        if self.kingMoves(square) & self.pieceSet(color, KING):
            return True
        bishopMoves = self.maskBlockedSquares(self.bishopMoves(square), square)
        if bishopMoves & (self.pieceSet(color, BISHOP) | self.pieceSet(color, QUEEN)):
            return True
        rookMoves = self.maskBlockedSquares(self.rookMoves(square), square)
        if rookMoves & (self.pieceSet(color, ROOK) | self.pieceSet(color, QUEEN)):
            return True
        return False

    def kingInCheck(self, color):
        """Checks if a player's king is in check."""
        kingSquare = self.bitScanForward(self.pieceSet(color, KING))
        if color in (RED, YELLOW):
            return self.attacked(kingSquare, BLUE) or self.attacked(kingSquare, GREEN), self.fileRank(kingSquare)
        else:
            return self.attacked(kingSquare, RED) or self.attacked(kingSquare, YELLOW), self.fileRank(kingSquare)

    def kingInCheckmate(self, current_player):
        """Checks if a player's king is in checkmate."""
        color = {'r': 0, 'b': 1, 'y': 2, 'g': 3}[current_player]
        # check if king in check
        check, king_pos = self.kingInCheck(color)
        if not check:
            return False
        # check if king can move
        king_square = self.square(king_pos[0], king_pos[1])
        if self.legalMoves(KING, king_square, color) != 0:
            return False
        # check if any of the pieces of king's color can move
        for piece_type in [PAWN, KNIGHT, BISHOP, ROOK, QUEEN]:
            for piece in self.getSquares(self.pieceSet(color, piece_type)):
                square = self.square(piece[0], piece[1])
                if self.legalMoves(piece_type, square, color) != 0:
                    return False
        # if playing in team, check if teammate can prevent checkmate
        # move of the teammate must be before player that gets checkmated
        # teammate = ['y', 'g', 'r', 'b']
        # if teammate[color] == current_player:
        #     return not self.checkIfTeammateCanPreventCheckmate(color)
        return True

    def checkIfCanCastle(self):
        pass

    def printBB(self, bitboard):
        """Prints 14x14 bitboard in easily readable format (for debugging)."""
        bitstring = ''
        for rank in reversed(range(14)):
            for file in range(14):
                if not ((file < 3 and rank < 3) or (file < 3 and rank > 10) or
                        (file > 10 and rank < 3) or (file > 10 and rank > 10)):
                    bitstring += '1 ' if (bitboard & (1 << self.square(file, rank))) else '. '
                else:
                    bitstring += '  '
            bitstring += '\n'
        print(bitstring)

    def printBB256(self, bitboard):
        """Prints full 256-bit (16x16) bitboard in easily readable format (for debugging)."""
        bitstring = ''
        for rank in reversed(range(16)):
            for file in range(16):
                bitstring += '1 ' if (bitboard & (1 << self.square256(file, rank))) else '. '
            bitstring += '\n'
        print(bitstring)

    def getPieceColor(self, char):
        """Returns piece type and color from two character identifier."""
        identifier = ['r', 'b', 'y', 'g', 'P', 'N', 'B', 'R', 'Q', 'K']
        color = identifier.index(char[0])
        piece = identifier.index(char[1])
        return piece, color

    def initBoard(self):
        """Initializes board with empty squares."""
        self.boardData = [' '] * self.files * self.ranks
        self.pieceBB = [0] * 10
        self.emptyBB = 0
        self.occupiedBB = 0
        # if 1, can castle, else cannot castle
        self.castlingState = [[1]*2 for _ in range(4)]
        self.castlingSquares = [[1 << self.square(5, 0), 1 << self.square(9, 0)],
                       [1 << self.square(0, 5), 1 << self.square(0, 9)],
                       [1 << self.square(8, 13), 1 << self.square(4, 13)],
                       [1 << self.square(13, 8), 1 << self.square(13, 4)]]
        self.rooksSquares = [[1 << self.square(3, 0), 1 << self.square(10, 0)],
                       [1 << self.square(0, 3), 1 << self.square(0, 10)],
                       [1 << self.square(10, 13), 1 << self.square(3, 13)],
                       [1 << self.square(13, 10), 1 << self.square(13, 3)]]
        self.castlingAvailability()
        self.boardReset.emit()

    def getData(self, file, rank):
        """Gets board data from square (file, rank)."""
        return self.boardData[file + rank * self.files]

    def setData(self, file, rank, data):
        """Sets board data at square (file, rank) to data."""
        index = file + rank * self.files
        if self.boardData[index] == data:
            return
        self.boardData[index] = data
        self.dataChanged.emit(file, rank)

    def makeMove(self, fromFile, fromRank, toFile, toRank, promote=None):
        """Moves piece from square (fromFile, fromRank) to square (toFile, toRank)."""
        # check if castling by castling square
        # if yes, than register move as castling by moving into rook square
        if (fromFile, fromRank, toFile, toRank) == (7, 0, 9, 0):  # red kingside
            toFile += 1
        elif (fromFile, fromRank, toFile, toRank) == (0, 7, 0, 9):  # blue kingside
            toRank += 1
        elif (fromFile, fromRank, toFile, toRank) == (6, 13, 4, 13):  # yellow kingside
            toFile -= 1
        elif (fromFile, fromRank, toFile, toRank) == (13, 6, 13, 4):  # green kingside
            toRank -= 1
        elif (fromFile, fromRank, toFile, toRank) == (7, 0, 5, 0):  # red queenside
            toFile -= 2
        elif (fromFile, fromRank, toFile, toRank) == (0, 7, 0, 5):  # blue queenside
            toRank -= 2
        elif (fromFile, fromRank, toFile, toRank) == (6, 13, 8, 13):  # yellow queenside
            toFile += 2
        elif (fromFile, fromRank, toFile, toRank) == (13, 6, 13, 8):  # green queenside
            toRank += 2

        char = self.getData(fromFile, fromRank)
        captured = self.getData(toFile, toRank)

        move = char + ' ' + chr(fromFile + 97) + str(fromRank + 1) + ' ' + \
               captured + ' ' + chr(toFile + 97) + str(toRank + 1)

        # If castling move, move king and rook to castling squares instead of ordinary move
        if move == 'rK h1 rR k1':  # kingside castle red by rook square
            self.setData(fromFile + 2, fromRank, char)
            self.setData(toFile - 2, toRank, captured)
            self.setData(fromFile, fromRank, ' ')
            self.setData(toFile, toRank, ' ')
            self.castlingState[RED][KINGSIDE] -= 1
        elif move == 'yK g14 yR d14':  # kingside castle yellow by rook square
            self.setData(fromFile - 2, fromRank, char)
            self.setData(toFile + 2, toRank, captured)
            self.setData(fromFile, fromRank, ' ')
            self.setData(toFile, toRank, ' ')
            self.castlingState[YELLOW][KINGSIDE] -= 1
        elif move == 'bK a8 bR a11':  # kingside castle blue by rook square
            self.setData(fromFile, fromRank + 2, char)
            self.setData(toFile, toRank - 2, captured)
            self.setData(fromFile, fromRank, ' ')
            self.setData(toFile, toRank, ' ')
            self.castlingState[BLUE][KINGSIDE] -= 1
        elif move == 'gK n7 gR n4':  # kingside castle green by rook square
            self.setData(fromFile, fromRank - 2, char)
            self.setData(toFile, toRank + 2, captured)
            self.setData(fromFile, fromRank, ' ')
            self.setData(toFile, toRank, ' ')
            self.castlingState[GREEN][KINGSIDE] -= 1
        elif move == 'rK h1 rR d1':  # queenside castle red
            self.setData(fromFile - 2, fromRank, char)
            self.setData(toFile + 3, toRank, captured)
            self.setData(fromFile, fromRank, ' ')
            self.setData(toFile, toRank, ' ')
            self.castlingState[RED][QUEENSIDE] -= 1
        elif move == 'yK g14 yR k14':  # queenside castle yellow
            self.setData(fromFile + 2, fromRank, char)
            self.setData(toFile - 3, toRank, captured)
            self.setData(fromFile, fromRank, ' ')
            self.setData(toFile, toRank, ' ')
            self.castlingState[YELLOW][QUEENSIDE] -= 1
        elif move == 'bK a8 bR a4':  # queenside castle blue
            self.setData(fromFile, fromRank - 2, char)
            self.setData(toFile, toRank + 3, captured)
            self.setData(fromFile, fromRank, ' ')
            self.setData(toFile, toRank, ' ')
            self.castlingState[BLUE][QUEENSIDE] -= 1
        elif move == 'gK n7 gR n11':  # queenside castle green
            self.setData(fromFile, fromRank + 2, char)
            self.setData(toFile, toRank - 3, captured)
            self.setData(fromFile, fromRank, ' ')
            self.setData(toFile, toRank, ' ')
            self.castlingState[GREEN][QUEENSIDE] -= 1
        else:  # regular move
            # move piece to target square
            self.setData(toFile, toRank, char)
            self.setData(fromFile, fromRank, ' ')
            # If king move or rook move from original square, remove castling availability
            if char == 'rK' and (fromFile, fromRank) == (7, 0):
                self.castlingState[RED][KINGSIDE] -= 1
                self.castlingState[RED][QUEENSIDE] -= 1
            if char == 'rR' and (fromFile, fromRank) == (10, 0):
                self.castlingState[RED][KINGSIDE] -= 1
            if char == 'rR' and (fromFile, fromRank) == (3, 0):
                self.castlingState[RED][QUEENSIDE] -= 1
            if char == 'bK' and (fromFile, fromRank) == (0, 7):
                self.castlingState[BLUE][KINGSIDE] -= 1
                self.castlingState[BLUE][QUEENSIDE] -= 1
            if char == 'bR' and (fromFile, fromRank) == (0, 10):
                self.castlingState[BLUE][KINGSIDE] -= 1
            if char == 'bR' and (fromFile, fromRank) == (0, 3):
                self.castlingSquares[BLUE][QUEENSIDE] = 0
                self.castlingState[BLUE][QUEENSIDE] -= 1
            if char == 'yK' and (fromFile, fromRank) == (6, 13):
                self.castlingState[YELLOW][KINGSIDE] -= 1
                self.castlingState[YELLOW][QUEENSIDE] -= 1
            if char == 'yR' and (fromFile, fromRank) == (3, 13):
                self.castlingState[YELLOW][KINGSIDE] -= 1
            if char == 'yR' and (fromFile, fromRank) == (10, 13):
                self.castlingState[YELLOW][QUEENSIDE] -= 1
            if char == 'gK' and (fromFile, fromRank) == (13, 6):
                self.castlingState[GREEN][KINGSIDE] -= 1
                self.castlingState[GREEN][QUEENSIDE] -= 1
            if char == 'gR' and (fromFile, fromRank) == (13, 3):
                self.castlingState[GREEN][KINGSIDE] -= 1
            if char == 'gR' and (fromFile, fromRank) == (13, 10):
                self.castlingState[GREEN][QUEENSIDE] -= 1
        # Update bitboards
        piece, color = self.getPieceColor(char)
        fromBB = 1 << self.square(fromFile, fromRank)
        toBB = 1 << self.square(toFile, toRank)
        fromToBB = fromBB ^ toBB
        # Move piece
        self.pieceBB[color] ^= fromToBB
        self.pieceBB[piece] ^= fromToBB
        self.occupiedBB ^= fromToBB
        self.emptyBB ^= fromToBB
        # check if any piece was captured
        if captured != ' ':
            piece_, color_ = self.getPieceColor(captured)
            if piece == KING and piece_ == ROOK and color == color_:
                # Undo king move
                self.pieceBB[color] ^= fromToBB
                self.pieceBB[piece] ^= fromToBB
                self.occupiedBB ^= fromToBB
                self.emptyBB ^= fromToBB
                # Move king and rook to proper castling squares
                pieceFromBB = 1 << self.square(fromFile, fromRank)
                pieceFromBB_ = 1 << self.square(toFile, toRank)
                if color == RED and toFile > fromFile:  # kingside castle red
                    pieceToBB = 1 << self.square(toFile - 1, toRank)
                    pieceToBB_ = 1 << self.square(toFile - 2, toRank)
                elif color == YELLOW and toFile < fromFile:  # kingside castle yellow
                    pieceToBB = 1 << self.square(toFile + 1, toRank)
                    pieceToBB_ = 1 << self.square(toFile + 2, toRank)
                elif color == BLUE and toRank > fromRank:  # kingside castle blue
                    pieceToBB = 1 << self.square(toFile, toRank - 1)
                    pieceToBB_ = 1 << self.square(toFile, toRank - 2)
                elif color == GREEN and toRank < fromRank:  # kingside castle green
                    pieceToBB = 1 << self.square(toFile, toRank + 1)
                    pieceToBB_ = 1 << self.square(toFile, toRank + 2)
                elif color == RED and toFile < fromFile:  # queenside castle red
                    pieceToBB = 1 << self.square(toFile + 2, toRank)
                    pieceToBB_ = 1 << self.square(toFile + 3, toRank)
                elif color == YELLOW and toFile > fromFile:  # queenside castle yellow
                    pieceToBB = 1 << self.square(toFile - 2, toRank)
                    pieceToBB_ = 1 << self.square(toFile - 3, toRank)
                elif color == BLUE and toRank < fromRank:  # queenside castle blue
                    pieceToBB = 1 << self.square(toFile, toRank + 2)
                    pieceToBB_ = 1 << self.square(toFile, toRank + 3)
                elif color == GREEN and toRank > fromRank:  # queenside castle green
                    pieceToBB = 1 << self.square(toFile, toRank - 2)
                    pieceToBB_ = 1 << self.square(toFile, toRank - 3)
                else:  # invalid move
                    pieceToBB = 0
                    pieceToBB_ = 0
                pieceFromToBB = pieceFromBB ^ pieceToBB
                pieceFromToBB_ = pieceFromBB_ ^ pieceToBB_
                # Move king
                self.pieceBB[color] ^= pieceFromToBB
                self.pieceBB[piece] ^= pieceFromToBB
                self.occupiedBB ^= pieceFromToBB
                self.emptyBB ^= pieceFromToBB
                # Move rook
                self.pieceBB[color_] ^= pieceFromToBB_
                self.pieceBB[piece_] ^= pieceFromToBB_
                self.occupiedBB ^= pieceFromToBB_
                self.emptyBB ^= pieceFromToBB_
                # Undo remove captured piece (in advance)
                self.pieceBB[color_] ^= toBB
                self.pieceBB[piece_] ^= toBB
                self.occupiedBB ^= toBB
                self.emptyBB ^= toBB
            elif piece_ == ROOK:
                # if your rook was taken, delete castling on this side
                if (toFile, toRank) == (10, 0):
                    self.castlingState[RED][KINGSIDE] -= 1
                elif (toFile, toRank) == (3, 0):
                    self.castlingState[RED][QUEENSIDE] -= 1
                elif (toFile, toRank) == (0, 10):
                    self.castlingState[BLUE][KINGSIDE] -= 1
                elif (toFile, toRank) == (0, 3):
                    self.castlingState[BLUE][QUEENSIDE] -= 1
                elif (toFile, toRank) == (3, 13):
                    self.castlingState[YELLOW][KINGSIDE] -= 1
                elif (toFile, toRank) == (10, 13):
                    self.castlingState[YELLOW][QUEENSIDE] -= 1
                elif (toFile, toRank) == (13, 3):
                    self.castlingState[GREEN][KINGSIDE] -= 1
                elif (toFile, toRank) == (13, 10):
                    self.castlingState[GREEN][QUEENSIDE] -= 1
            # Remove captured piece
            self.pieceBB[color_] ^= toBB
            self.pieceBB[piece_] ^= toBB
            self.occupiedBB ^= toBB
            self.emptyBB ^= toBB
        if promote is not None:
            promoteChar = {RED: 'r', BLUE: 'b', YELLOW: 'y', GREEN: 'g', QUEEN: 'Q', KNIGHT: 'N', ROOK: 'R', BISHOP: 'B'}
            self.setData(toFile, toRank, f'{promoteChar[color]}{promoteChar[promote]}')
            self.pieceBB[PAWN] ^= toBB
            self.pieceBB[promote] ^= toBB
        # Emit signal for board view auto-rotation
        self.autoRotate.emit(-1)

    def undoMove(self, fromFile, fromRank, toFile, toRank, char, captured, promote):
        """Takes back move and restores captured piece."""
        # Remove king and rook from castling squares
        if (fromFile, fromRank, toFile, toRank) == (7, 0, 9, 0):  # red kingside
            toFile += 1
            captured = 'rR'
        elif (fromFile, fromRank, toFile, toRank) == (0, 7, 0, 9):  # blue kingside
            toRank += 1
            captured = 'bR'
        elif (fromFile, fromRank, toFile, toRank) == (6, 13, 4, 13):  # yellow kingside
            toFile -= 1
            captured = 'yR'
        elif (fromFile, fromRank, toFile, toRank) == (13, 6, 13, 4):  # green kingside
            toRank -= 1
            captured = 'gR'
        elif (fromFile, fromRank, toFile, toRank) == (7, 0, 5, 0):  # red queenside
            toFile -= 2
            captured = 'rR'
        elif (fromFile, fromRank, toFile, toRank) == (0, 7, 0, 5):  # blue queenside
            toRank -= 2
            captured = 'bR'
        elif (fromFile, fromRank, toFile, toRank) == (6, 13, 8, 13):  # yellow queenside
            toFile += 2
            captured = 'yR'
        elif (fromFile, fromRank, toFile, toRank) == (13, 6, 13, 8):  # green queenside
            toRank += 2
            captured = 'gR'
        move = char + ' ' + chr(fromFile + 97) + str(fromRank + 1) + ' ' + \
               captured + ' ' + chr(toFile + 97) + str(toRank + 1)
        if move == 'rK h1 rR k1':  # kingside castle red
            self.setData(fromFile + 2, fromRank, ' ')
            self.setData(toFile - 2, toRank, ' ')
            self.castlingState[RED][KINGSIDE] += 1
        elif move == 'yK g14 yR d14':  # kingside castle yellow
            self.setData(fromFile - 2, fromRank, ' ')
            self.setData(toFile + 2, toRank, ' ')
            self.castlingState[YELLOW][KINGSIDE] += 1
        elif move == 'bK a8 bR a11':  # kingside castle blue
            self.setData(fromFile, fromRank + 2, ' ')
            self.setData(toFile, toRank - 2, ' ')
            self.castlingState[BLUE][KINGSIDE] += 1
        elif move == 'gK n7 gR n4':  # kingside castle green
            self.setData(fromFile, fromRank - 2, ' ')
            self.setData(toFile, toRank + 2, ' ')
            self.castlingState[GREEN][KINGSIDE] += 1
        elif move == 'rK h1 rR d1':  # queenside castle red
            self.setData(fromFile - 2, fromRank, ' ')
            self.setData(toFile + 3, toRank, ' ')
            self.castlingState[RED][QUEENSIDE] += 1
        elif move == 'yK g14 yR k14':  # queenside castle yellow
            self.setData(fromFile + 2, fromRank, ' ')
            self.setData(toFile - 3, toRank, ' ')
            self.castlingState[YELLOW][QUEENSIDE] += 1
        elif move == 'bK a8 bR a4':  # queenside castle blue
            self.setData(fromFile, fromRank - 2, ' ')
            self.setData(toFile, toRank + 3, ' ')
            self.castlingState[BLUE][QUEENSIDE] += 1
        elif move == 'gK n7 gR n11':  # queenside castle green
            self.setData(fromFile, fromRank + 2, ' ')
            self.setData(toFile, toRank - 3, ' ')
            self.castlingState[GREEN][QUEENSIDE] += 1
        else:
            if char == 'rK' and (fromFile, fromRank) == (7, 0):
                self.castlingState[RED][KINGSIDE] += 1
                self.castlingState[RED][QUEENSIDE] += 1
            if char == 'rR' and (fromFile, fromRank) == (10, 0):
                self.castlingState[RED][KINGSIDE] += 1
            if char == 'rR' and (fromFile, fromRank) == (3, 0):
                self.castlingState[RED][QUEENSIDE] += 1
            if char == 'bK' and (fromFile, fromRank) == (0, 7):
                self.castlingState[BLUE][KINGSIDE] += 1
                self.castlingState[BLUE][QUEENSIDE] += 1
            if char == 'bR' and (fromFile, fromRank) == (0, 10):
                self.castlingState[BLUE][KINGSIDE] += 1
            if char == 'bR' and (fromFile, fromRank) == (0, 3):
                self.castlingState[BLUE][QUEENSIDE] += 1
            if char == 'yK' and (fromFile, fromRank) == (6, 13):
                self.castlingState[YELLOW][KINGSIDE] += 1
                self.castlingState[YELLOW][QUEENSIDE] += 1
            if char == 'yR' and (fromFile, fromRank) == (3, 13):
                self.castlingState[YELLOW][KINGSIDE] += 1
            if char == 'yR' and (fromFile, fromRank) == (10, 13):
                self.castlingState[YELLOW][QUEENSIDE] += 1
            if char == 'gK' and (fromFile, fromRank) == (13, 6):
                self.castlingState[GREEN][KINGSIDE] += 1
                self.castlingState[GREEN][QUEENSIDE] += 1
            if char == 'gR' and (fromFile, fromRank) == (13, 3):
                self.castlingState[GREEN][KINGSIDE] += 1
            if char == 'gR' and (fromFile, fromRank) == (13, 10):
                self.castlingState[GREEN][QUEENSIDE] += 1
        # Move piece back and restore captured piece
        self.setData(fromFile, fromRank, char)
        self.setData(toFile, toRank, captured)
        # Update bitboards
        piece, color = self.getPieceColor(char)
        fromBB = 1 << self.square(toFile, toRank)
        toBB = 1 << self.square(fromFile, fromRank)
        fromToBB = fromBB ^ toBB
        # Move piece back
        self.pieceBB[color] ^= fromToBB
        self.pieceBB[piece] ^= fromToBB
        self.occupiedBB ^= fromToBB
        self.emptyBB ^= fromToBB

        if captured != ' ':
            piece_, color_ = self.getPieceColor(captured)
            if piece == KING and piece_ == ROOK and color == color_:
                # Undo king move
                self.pieceBB[color] ^= fromToBB
                self.pieceBB[piece] ^= fromToBB
                self.occupiedBB ^= fromToBB
                self.emptyBB ^= fromToBB

                # Move king and rook to proper squares
                pieceToBB = 1 << self.square(fromFile, fromRank)
                pieceToBB_ = 1 << self.square(toFile, toRank)
                if color == RED and toFile > fromFile:  # kingside castle red
                    pieceFromBB = 1 << self.square(toFile - 1, toRank)
                    pieceFromBB_ = 1 << self.square(toFile - 2, toRank)
                elif color == YELLOW and toFile < fromFile:  # kingside castle yellow
                    pieceFromBB = 1 << self.square(toFile + 1, toRank)
                    pieceFromBB_ = 1 << self.square(toFile + 2, toRank)
                elif color == BLUE and toRank > fromRank:  # kingside castle blue
                    pieceFromBB = 1 << self.square(toFile, toRank - 1)
                    pieceFromBB_ = 1 << self.square(toFile, toRank - 2)
                elif color == GREEN and toRank < fromRank:  # kingside castle green
                    pieceFromBB = 1 << self.square(toFile, toRank + 1)
                    pieceFromBB_ = 1 << self.square(toFile, toRank + 2)
                elif color == RED and toFile < fromFile:  # queenside castle red
                    pieceFromBB = 1 << self.square(toFile + 2, toRank)
                    pieceFromBB_ = 1 << self.square(toFile + 3, toRank)
                elif color == YELLOW and toFile > fromFile:  # queenside castle yellow
                    pieceFromBB = 1 << self.square(toFile - 2, toRank)
                    pieceFromBB_ = 1 << self.square(toFile - 3, toRank)
                elif color == BLUE and toRank < fromRank:  # queenside castle blue
                    pieceFromBB = 1 << self.square(toFile, toRank + 2)
                    pieceFromBB_ = 1 << self.square(toFile, toRank + 3)
                elif color == GREEN and toRank > fromRank:  # queenside castle green
                    pieceFromBB = 1 << self.square(toFile, toRank - 2)
                    pieceFromBB_ = 1 << self.square(toFile, toRank - 3)
                else:  # invalid move
                    pieceFromBB = 0
                    pieceFromBB_ = 0

                pieceFromToBB = pieceFromBB ^ pieceToBB
                pieceFromToBB_ = pieceFromBB_ ^ pieceToBB_
                # Move king
                self.pieceBB[color] ^= pieceFromToBB
                self.pieceBB[piece] ^= pieceFromToBB
                self.occupiedBB ^= pieceFromToBB
                self.emptyBB ^= pieceFromToBB
                # Move rook
                self.pieceBB[color_] ^= pieceFromToBB_
                self.pieceBB[piece_] ^= pieceFromToBB_
                self.occupiedBB ^= pieceFromToBB_
                self.emptyBB ^= pieceFromToBB_
                # Undo restore captured piece (in advance)
                self.pieceBB[color_] ^= fromBB
                self.pieceBB[piece_] ^= fromBB
                self.occupiedBB ^= fromBB
                self.emptyBB ^= fromBB

            elif piece_ == ROOK:
                # if your rook was previously taken, restore castling on this side
                if (toFile, toRank) == (10, 0):
                    self.castlingState[RED][KINGSIDE] += 1
                elif (toFile, toRank) == (3, 0):
                    self.castlingState[RED][QUEENSIDE] += 1
                elif (toFile, toRank) == (0, 10):
                    self.castlingState[BLUE][KINGSIDE] += 1
                elif (toFile, toRank) == (0, 3):
                    self.castlingState[BLUE][QUEENSIDE] += 1
                elif (toFile, toRank) == (3, 13):
                    self.castlingState[YELLOW][KINGSIDE] += 1
                elif (toFile, toRank) == (10, 13):
                    self.castlingState[YELLOW][QUEENSIDE] += 1
                elif (toFile, toRank) == (13, 3):
                    self.castlingState[GREEN][KINGSIDE] += 1
                elif (toFile, toRank) == (13, 10):
                    self.castlingState[GREEN][QUEENSIDE] += 1
            # Restore captured piece
            self.pieceBB[color_] ^= fromBB
            self.pieceBB[piece_] ^= fromBB
            self.occupiedBB ^= fromBB
            self.emptyBB ^= fromBB
        # Emit signal for board view auto-
        if promote is not None:
            self.pieceBB[PAWN] ^= fromBB
            self.pieceBB[promote] ^= fromBB
        self.autoRotate.emit(1)

    def castlingAvailability(self):
        """Returns castling availability string."""
        castling = ''
        color_name = {0: 'r', 1: 'b', 2: 'y', 3: 'g'}
        # "K" if kingside castling available, "Q" if queenside, "-" if no player can castle
        for color in [RED, BLUE, YELLOW, GREEN]:
            if self.castlingState[color][KINGSIDE] == 1:
                castling += f'{color_name[color]}K'
            if self.castlingState[color][QUEENSIDE] == 1:
                castling += f'{color_name[color]}Q'
        if not castling:
            castling = '-'
        return castling

    def parseFen4(self, fen4):
        """Sets board position according to the FEN4 string fen4."""
        if SETTINGS.checkSetting('chesscom'):
            # Remove chess.com prefix and commas
            i = fen4.rfind('-')
            fen4 = fen4[i+1:]
            fen4 = fen4.replace(',', '')
            fen4 += ' '
        index = 0
        skip = 0
        for rank in reversed(range(self.ranks)):
            for file in range(self.files):
                if skip > 0:
                    char = ' '
                    skip -= 1
                else:
                    # Pieces are always two characters, skip value can be single or double digit
                    char = fen4[index]
                    index += 1
                    if char.isdigit():
                        # Check if next is also digit. If yes, treat as single number
                        next_ = fen4[index]
                        if next_.isdigit():
                            char += next_
                            index += 1
                        skip = int(char)
                        char = ' '
                        skip -= 1
                    # If not digit, then it is a two-character piece. Add next character
                    else:
                        char += fen4[index]
                        index += 1
                self.setData(file, rank, char)
                # Set bitboards
                if char != ' ':
                    piece, color = self.getPieceColor(char)
                    self.pieceBB[color] |= 1 << self.square(file, rank)
                    self.pieceBB[piece] |= 1 << self.square(file, rank)
            next_ = fen4[index]
            if next_ != '/' and next_ != ' ':
                # If no slash or space after rank, the FEN4 is invalid, so reset board
                self.initBoard()
                return
            else:  # Skip the slash
                index += 1
        self.occupiedBB = self.pieceBB[RED] | self.pieceBB[BLUE] | self.pieceBB[YELLOW] | self.pieceBB[GREEN]
        self.emptyBB = ~self.occupiedBB
        self.boardReset.emit()

    def getFen4(self):
        """Generates FEN4 from current board state."""
        fen4 = ''
        skip = 0
        prev = ' '
        for rank in reversed(range(self.ranks)):
            for file in range(self.files):
                char = self.getData(file, rank)
                # If current square is empty, increment skip value
                if char == ' ':
                    skip += 1
                    prev = char
                else:
                    # If current square is not empty, but previous square was empty, append skip value to FEN4 string,
                    # unless the previous square was on the previous rank
                    if prev == ' ' and file != 0:
                        fen4 += str(skip)
                        skip = 0
                    # Append algebraic piece name to FEN4 string
                    fen4 += char
                    prev = char
            # If skip is non-zero at end of rank, append skip and reset to zero
            if skip > 0:
                fen4 += str(skip)
                skip = 0
            # Append slash at end of rank and append space after last rank
            if rank == 0:
                fen4 += ' '
            else:
                fen4 += '/'
        return fen4

    def getChesscomFen4(self):
        """Generates chess.com compatible FEN4."""
        fen4 = ''
        skip = 0
        prev = ' '
        for rank in reversed(range(self.ranks)):
            for file in range(self.files):
                char = self.getData(file, rank)
                # If current square is empty, increment skip value
                if char == ' ':
                    skip += 1
                    prev = char
                else:
                    # If current square is not empty, but previous square was empty, append skip value to FEN4 string,
                    # unless the previous square was on the previous rank
                    if prev == ' ' and file != 0:
                        fen4 += str(skip) + ','
                        skip = 0
                    # Append algebraic piece name to FEN4 string
                    fen4 += char + ','
                    prev = char
            # If skip is non-zero at end of rank, append skip and reset to zero
            if skip > 0:
                fen4 += str(skip) + ','
                skip = 0
            # Append slash at end of rank
            if rank != 0:
                fen4 = fen4[:-1]
                fen4 += '/'
        fen4 = fen4[:-1]
        return fen4
