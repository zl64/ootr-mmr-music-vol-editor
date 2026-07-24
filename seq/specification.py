from dataclasses import dataclass

from .constants import BitField, BITFIELDS
from .enums import ALL_SECTIONS, ALL_VERSIONS, DataType, SeqSection, SeqVersion


@dataclass
class Spec:
    opcode: int
    name: str
    operands: tuple[DataType, ...] = ()
    bitmask: BitField | None = None
    sections: tuple[SeqSection, ...] = ALL_SECTIONS
    versions: tuple[SeqVersion, ...] = ALL_VERSIONS
    is_pointer: bool = False

    @property
    def is_bitfield(self):
        return self.bitmask is not None

    def matches(self, opcode: int, section: SeqSection, version: SeqVersion) -> bool:
        if section not in self.sections:
            return False

        if version not in self.versions:
            return False

        if self.is_bitfield:
            return (opcode & self.bitmask.opcode_mask) == self.opcode

        return opcode == self.opcode


SPECS = [
    #region Control Flow
    Spec(0xFF, 'end',),
    Spec(0xFE, 'delay1',),
    Spec(0xFD, 'delay',          operands=(DataType.COMPRESSED_U16,),),
    Spec(0xFC, 'call',           operands=(DataType.U16,), is_pointer=True,),
    Spec(0xFB, 'jump',           operands=(DataType.U16,),),
    Spec(0xFA, 'beqz',           operands=(DataType.U16,),),
    Spec(0xF9, 'bltz',           operands=(DataType.U16,),),
    Spec(0xF8, 'loop',           operands=(DataType.U8,),),
    Spec(0xF7, 'loopend',),
    Spec(0xF6, 'break',),
    Spec(0xF5, 'bgez',           operands=(DataType.U16,),),
    Spec(0xF4, 'rjump',          operands=(DataType.U8,),),
    Spec(0xF3, 'rbeqz',          operands=(DataType.U8,),),
    Spec(0xF2, 'rbltz',          operands=(DataType.U8,),),
    #endregion Control Flow

    #region Header
    # Non-Argbit
    Spec(0xF1, 'allocnotelist',  operands=(DataType.U8,),               sections=(SeqSection.HEADER,)),
    Spec(0xF0, 'freenotelist',   operands=(DataType.U8,),               sections=(SeqSection.HEADER,)),
    Spec(0xEF, 'hd_EF',          operands=(DataType.S16, DataType.U8),  sections=(SeqSection.HEADER,)),
    Spec(0xDF, 'transpose',      operands=(DataType.U8,),               sections=(SeqSection.HEADER,)),
    Spec(0xDE, 'rtranspose',     operands=(DataType.U8,),               sections=(SeqSection.HEADER,)),
    Spec(0xDD, 'tempo',          operands=(DataType.U8,),               sections=(SeqSection.HEADER,)),
    Spec(0xDC, 'tempochg',       operands=(DataType.U8,),               sections=(SeqSection.HEADER,)),
    Spec(0xDB, 'vol',            operands=(DataType.U8,),               sections=(SeqSection.HEADER,)),
    Spec(0xDA, 'volmode',        operands=(DataType.U8, DataType.U16),  sections=(SeqSection.HEADER,)),
    Spec(0xD9, 'volscale',       operands=(DataType.U8,),               sections=(SeqSection.HEADER,)),
    Spec(0xD7, 'initchan',       operands=(DataType.U16,),              sections=(SeqSection.HEADER,)),
    Spec(0xD6, 'freechan',       operands=(DataType.U16,),              sections=(SeqSection.HEADER,)),
    Spec(0xD5, 'mutescale',      operands=(DataType.U8,),               sections=(SeqSection.HEADER,)),
    Spec(0xD4, 'mute',                                                  sections=(SeqSection.HEADER,)),
    Spec(0xD3, 'mutebhv',        operands=(DataType.U8,),               sections=(SeqSection.HEADER,)),
    Spec(0xD2, 'ldshortvelarr',  operands=(DataType.U16,),              sections=(SeqSection.HEADER,)),
    Spec(0xD1, 'ldshortgatearr', operands=(DataType.U16,),              sections=(SeqSection.HEADER,)),
    Spec(0xD0, 'notealloc',      operands=(DataType.U8,),               sections=(SeqSection.HEADER,)),
    Spec(0xCE, 'rand',           operands=(DataType.U8,),               sections=(SeqSection.HEADER,)),
    Spec(0xCD, 'dyncall',        operands=(DataType.U16,),              sections=(SeqSection.HEADER,)),
    Spec(0xCC, 'ldi',            operands=(DataType.U8,),               sections=(SeqSection.HEADER,)),
    Spec(0xC9, 'and',            operands=(DataType.U8,),               sections=(SeqSection.HEADER,)),
    Spec(0xC8, 'sub',            operands=(DataType.U8,),               sections=(SeqSection.HEADER,)),
    Spec(0xC7, 'stseq',          operands=(DataType.U8, DataType.U16,), sections=(SeqSection.HEADER,)),
    Spec(0xC6, 'stop',                                                  sections=(SeqSection.HEADER,)),
    Spec(0xC5, 'scriptctr',      operands=(DataType.U16,),              sections=(SeqSection.HEADER,)),
    Spec(0xC4, 'runseq',         operands=(DataType.U8, DataType.U8),   sections=(SeqSection.HEADER,)),
    # MM ONLY
    Spec(0xC3, 'hd_C3',          operands=(DataType.U16,),              sections=(SeqSection.HEADER,), versions=(SeqVersion.MAJORAS_MASK,)),
    Spec(0xC2, 'hd_C2',          operands=(DataType.S16,),              sections=(SeqSection.HEADER,), versions=(SeqVersion.MAJORAS_MASK,)),

    # Argbit
    Spec(0xB0, 'ldseq',          operands=(DataType.U8, DataType.U16,), sections=(SeqSection.HEADER,), bitmask=BITFIELDS[4],),
    Spec(0xA0, 'rldchan',        operands=(DataType.S16,),              sections=(SeqSection.HEADER,), bitmask=BITFIELDS[4],),
    Spec(0x90, 'ldchan',         operands=(DataType.U16,),              sections=(SeqSection.HEADER,), bitmask=BITFIELDS[4], is_pointer=True,),
    Spec(0x80, 'ldio',                                                  sections=(SeqSection.HEADER,), bitmask=BITFIELDS[3],),
    Spec(0x70, 'stio',                                                  sections=(SeqSection.HEADER,), bitmask=BITFIELDS[3],),
    Spec(0x60, 'ldres',          operands=(DataType.U8, DataType.U8,),  sections=(SeqSection.HEADER,), bitmask=BITFIELDS[4],),
    Spec(0x50, 'subio',                                                 sections=(SeqSection.HEADER,), bitmask=BITFIELDS[3],),
    Spec(0x40, 'stopchan',                                              sections=(SeqSection.HEADER,), bitmask=BITFIELDS[4],),
    Spec(0x00, 'testchan',                                              sections=(SeqSection.HEADER,), bitmask=BITFIELDS[4],),
    #endregion Header

    #region Channel
    # Non-Argbit
    Spec(0xF1, 'allocnotelist', operands=(DataType.U8,),                           sections=(SeqSection.CHANNEL,),),
    Spec(0xF0, 'freenotelist',                                                     sections=(SeqSection.CHANNEL,),),
    Spec(0xEE, 'bend2',         operands=(DataType.S8,),                           sections=(SeqSection.CHANNEL,),),
    Spec(0xED, 'gain',          operands=(DataType.U8,),                           sections=(SeqSection.CHANNEL,),),
    Spec(0xEC, 'resetparams',                                                      sections=(SeqSection.CHANNEL,),),
    Spec(0xEB, 'fontinstr',     operands=(DataType.U8, DataType.U8,),              sections=(SeqSection.CHANNEL,),),
    Spec(0xEA, 'stop',                                                             sections=(SeqSection.CHANNEL,),),
    Spec(0xE9, 'notepri',       operands=(DataType.U8,),                           sections=(SeqSection.CHANNEL,),),
    Spec(0xE8, 'params',        operands=(DataType.U8, DataType.U8, DataType.U8, DataType.S8, DataType.S8, DataType.U8, DataType.U8, DataType.U8,), sections=(SeqSection.CHANNEL,),),
    Spec(0xE7, 'ldparams',      operands=(DataType.U16,),                          sections=(SeqSection.CHANNEL,),),
    Spec(0xE6, 'samplebook',    operands=(DataType.U8,),                           sections=(SeqSection.CHANNEL,),),
    Spec(0xE5, 'reverbidx',     operands=(DataType.U8,),                           sections=(SeqSection.CHANNEL,),),
    Spec(0xE4, 'dyncall',                                                          sections=(SeqSection.CHANNEL,),),
    Spec(0xE3, 'vibdelay',      operands=(DataType.U8,),                           sections=(SeqSection.CHANNEL,),),
    Spec(0xE2, 'vibdepthgrad',  operands=(DataType.U8, DataType.U8, DataType.U8,), sections=(SeqSection.CHANNEL,),),
    Spec(0xE1, 'vibfreqgrad',   operands=(DataType.U8, DataType.U8, DataType.U8,), sections=(SeqSection.CHANNEL,),),
    Spec(0xE0, 'volexp',        operands=(DataType.U8,),                           sections=(SeqSection.CHANNEL,),),
    Spec(0xDF, 'vol',           operands=(DataType.U8,),                           sections=(SeqSection.CHANNEL,),),
    Spec(0xDE, 'freqscale',     operands=(DataType.U16,),                          sections=(SeqSection.CHANNEL,),),
    Spec(0xDD, 'pan',           operands=(DataType.U8,),                           sections=(SeqSection.CHANNEL,),),
    Spec(0xDC, 'panweight',     operands=(DataType.U8,),                           sections=(SeqSection.CHANNEL,),),
    Spec(0xDB, 'transpose',     operands=(DataType.S8,),                           sections=(SeqSection.CHANNEL,),),
    Spec(0xDA, 'env',           operands=(DataType.U16,),                          sections=(SeqSection.CHANNEL,),),
    Spec(0xD9, 'releaserate',   operands=(DataType.U8,),                           sections=(SeqSection.CHANNEL,),),
    Spec(0xD8, 'vibdepth',      operands=(DataType.U8,),                           sections=(SeqSection.CHANNEL,),),
    Spec(0xD7, 'vibfreq',       operands=(DataType.U8,),                           sections=(SeqSection.CHANNEL,),),
    Spec(0xD4, 'reverb',        operands=(DataType.U8,),                           sections=(SeqSection.CHANNEL,),),
    Spec(0xD3, 'bend12',        operands=(DataType.S8,),                           sections=(SeqSection.CHANNEL,),),
    Spec(0xD2, 'sustain',       operands=(DataType.U8,),                           sections=(SeqSection.CHANNEL,),),
    Spec(0xD1, 'notealloc',     operands=(DataType.U8,),                           sections=(SeqSection.CHANNEL,),),
    Spec(0xD0, 'effects',       operands=(DataType.U8,),                           sections=(SeqSection.CHANNEL,),),
    Spec(0xCF, 'stptrtoseq',    operands=(DataType.U16,),                          sections=(SeqSection.CHANNEL,),),
    Spec(0xCE, 'ldptr',         operands=(DataType.U16,),                          sections=(SeqSection.CHANNEL,),),
    Spec(0xCD, 'stopchan',      operands=(DataType.U8,),                           sections=(SeqSection.CHANNEL,),),
    Spec(0xCC, 'ldi',           operands=(DataType.U8,),                           sections=(SeqSection.CHANNEL,),),
    Spec(0xCB, 'ldseq',         operands=(DataType.U16,),                          sections=(SeqSection.CHANNEL,),),
    Spec(0xCA, 'mutebhv',       operands=(DataType.U8,),                           sections=(SeqSection.CHANNEL,),),
    Spec(0xC9, 'and',           operands=(DataType.U8,),                           sections=(SeqSection.CHANNEL,),),
    Spec(0xC8, 'sub',           operands=(DataType.U8,),                           sections=(SeqSection.CHANNEL,),),
    Spec(0xC7, 'stseq',         operands=(DataType.U8, DataType.U16,),             sections=(SeqSection.CHANNEL,),),
    Spec(0xC6, 'font',          operands=(DataType.U8,),                           sections=(SeqSection.CHANNEL,),),
    Spec(0xC5, 'dyntbllookup',                                                     sections=(SeqSection.CHANNEL,),),
    Spec(0xC4, 'legato',                                                           sections=(SeqSection.CHANNEL,),),
    Spec(0xC3, 'nolegato',                                                         sections=(SeqSection.CHANNEL,),),
    Spec(0xC2, 'dyntbl',        operands=(DataType.U16,),                          sections=(SeqSection.CHANNEL,),),
    Spec(0xC1, 'instr',         operands=(DataType.U8,),                           sections=(SeqSection.CHANNEL,),),
    Spec(0xBE, 'ch_BE',         operands=(DataType.U8,),                           sections=(SeqSection.CHANNEL,), versions=(SeqVersion.MAJORAS_MASK,),),
    Spec(0xBD, 'randptr',       operands=(DataType.U16, DataType.U16,),            sections=(SeqSection.CHANNEL,), versions=(SeqVersion.OCARINA_OF_TIME,),),
    Spec(0xBD, 'samplestart',   operands=(DataType.U8,),                           sections=(SeqSection.CHANNEL,), versions=(SeqVersion.MAJORAS_MASK,),),
    Spec(0xBC, 'ptradd',        operands=(DataType.U16,),                          sections=(SeqSection.CHANNEL,),),
    Spec(0xBB, 'combfilter',    operands=(DataType.U8, DataType.U16,),             sections=(SeqSection.CHANNEL,),),
    Spec(0xBA, 'randgate',      operands=(DataType.U8,),                           sections=(SeqSection.CHANNEL,),),
    Spec(0xB9, 'randvel',       operands=(DataType.U8,),                           sections=(SeqSection.CHANNEL,),),
    Spec(0xB8, 'rand',          operands=(DataType.U8,),                           sections=(SeqSection.CHANNEL,),),
    Spec(0xB7, 'randtoptr',     operands=(DataType.U16,),                          sections=(SeqSection.CHANNEL,),),
    Spec(0xB6, 'dyntblv',                                                          sections=(SeqSection.CHANNEL,),),
    Spec(0xB5, 'dyntbltoptr',                                                      sections=(SeqSection.CHANNEL,),),
    Spec(0xB4, 'ptrtodyntbl',                                                      sections=(SeqSection.CHANNEL,),),
    Spec(0xB3, 'filter',        operands=(DataType.U8,),                           sections=(SeqSection.CHANNEL,),),
    Spec(0xB2, 'ldseqtoptr',    operands=(DataType.U16,),                          sections=(SeqSection.CHANNEL,),),
    Spec(0xB1, 'freefilter',                                                       sections=(SeqSection.CHANNEL,),),
    Spec(0xB0, 'ldfilter',      operands=(DataType.U16,),                          sections=(SeqSection.CHANNEL,),),
    Spec(0xA8, 'randptr',       operands=(DataType.U16, DataType.U16,),            sections=(SeqSection.CHANNEL,), versions=(SeqVersion.MAJORAS_MASK,),),
    Spec(0xA7, 'ch_A7',         operands=(DataType.U8,),                           sections=(SeqSection.CHANNEL,), versions=(SeqVersion.MAJORAS_MASK,),),
    Spec(0xA6, 'ch_A6',         operands=(DataType.U8, DataType.S16,),             sections=(SeqSection.CHANNEL,), versions=(SeqVersion.MAJORAS_MASK,),),
    Spec(0xA5, 'ch_A5',                                                            sections=(SeqSection.CHANNEL,), versions=(SeqVersion.MAJORAS_MASK,),),
    Spec(0xA4, 'ch_A4',         operands=(DataType.U8,),                           sections=(SeqSection.CHANNEL,), versions=(SeqVersion.MAJORAS_MASK,),),
    Spec(0xA3, 'ch_A3',                                                            sections=(SeqSection.CHANNEL,), versions=(SeqVersion.MAJORAS_MASK,),),
    Spec(0xA2, 'ch_A2',         operands=(DataType.S16,),                          sections=(SeqSection.CHANNEL,), versions=(SeqVersion.MAJORAS_MASK,),),
    Spec(0xA1, 'ch_A1',                                                            sections=(SeqSection.CHANNEL,), versions=(SeqVersion.MAJORAS_MASK,),),
    Spec(0xA0, 'ch_A0',         operands=(DataType.S16,),                          sections=(SeqSection.CHANNEL,), versions=(SeqVersion.MAJORAS_MASK,),),

    # Argbit
    Spec(0x98, 'dynldlayer',                                                       sections=(SeqSection.CHANNEL,), bitmask=BITFIELDS[3],),
    Spec(0x90, 'dellayer',                                                         sections=(SeqSection.CHANNEL,), bitmask=BITFIELDS[3],),
    Spec(0x88, 'ldlayer',       operands=(DataType.U16,),                          sections=(SeqSection.CHANNEL,), bitmask=BITFIELDS[3],),
    Spec(0x80, 'testlayer',                                                        sections=(SeqSection.CHANNEL,), bitmask=BITFIELDS[3],),
    Spec(0x78, 'rldlayer',      operands=(DataType.U16,),                          sections=(SeqSection.CHANNEL,), bitmask=BITFIELDS[3],),
    Spec(0x70, 'stio',                                                             sections=(SeqSection.CHANNEL,), bitmask=BITFIELDS[3],),
    Spec(0x60, 'ldio',                                                             sections=(SeqSection.CHANNEL,), bitmask=BITFIELDS[3],),
    Spec(0x50, 'subio',                                                            sections=(SeqSection.CHANNEL,), bitmask=BITFIELDS[3],),
    Spec(0x40, 'ldcio',         operands=(DataType.U8,),                           sections=(SeqSection.CHANNEL,), bitmask=BITFIELDS[4],),
    Spec(0x30, 'stcio',         operands=(DataType.U8,),                           sections=(SeqSection.CHANNEL,), bitmask=BITFIELDS[4],),
    Spec(0x20, 'ldchan',        operands=(DataType.U16,),                          sections=(SeqSection.CHANNEL,), bitmask=BITFIELDS[4], is_pointer=True,),
    Spec(0x18, 'ldsample',                                                         sections=(SeqSection.CHANNEL,), bitmask=BITFIELDS[3],),
    Spec(0x10, 'ldsample',                                                         sections=(SeqSection.CHANNEL,), bitmask=BITFIELDS[3],),
    Spec(0x00, 'cdelay',                                                           sections=(SeqSection.CHANNEL,), bitmask=BITFIELDS[4],),
    #endregion Channel

    #region Note Layer
    #endregion Note Layer
]
