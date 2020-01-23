import OntRemote

class Phys:
    def __init__(self, mp):
        self.TX = OntRemote.Scpi.ParameterGroup(mp, 'PHYS TX')
        self.TX.addParameters( ( ('Linerate', ':SOUR:DATA:TEL:PHYS:LINE:RATE'),
                                 ('Transponder', ':OUTP:TEL:PHYS:LINE:TYPE'),
                                 ('Laser', ':OUTP:TEL:PHYS:LINE:OPT:STAT')))
        self.RX = OntRemote.Scpi.ParameterGroup(mp, 'PHYS RX')
        self.RX.addParameters( ( ('Linerate', ':SENS:DATA:TEL:PHYS:LINE:RATE'),
                                 ('Transponder', ':INP:TEL:PHYS:LINE:TYPE')))