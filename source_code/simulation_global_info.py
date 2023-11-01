# Default value for multiplier use to tune the adaptive time step (used if user 
# specifies none in input file transitory_input.xlsx)
MLT_DEFAULT_VALUE = dict(
    MLT_INCREASE = 1.2, # multiplier to increase the adaptive time step
    MLT_DECREASE = 0.5, # multiplier to reduce the adaptive time step
)