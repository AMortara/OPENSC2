# Flags for the current definition

# Constant value read from input file conductor_definition.xlsx
IOP_CONSTANT = 0
# Initial current spatial distribution load form auxiliary input file
IOP_FROM_FILE = -1
# Current beavior as function of space and time from user defined function
IOP_FROM_EXT_FUNCTION = -2

# Flags for electric conductance

# Electric conductance is defined per unit length
ELECTRIC_CONDUCTANCE_UNIT_LENGTH = 1
# Electric conductance is not defined per unit length
ELECTRIC_CONDUCTANCE_NOT_UNIT_LENGTH = 2