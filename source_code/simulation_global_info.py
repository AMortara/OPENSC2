# Default value for multiplier use to tune the adaptive time step (used if user 
# specifies none in input file transitory_input.xlsx)
MLT_DEFAULT_VALUE = dict(
    MLT_INCREASE = 1.2, # multiplier to increase the adaptive time step
    MLT_DECREASE = 0.5, # multiplier to reduce the adaptive time step
)

# Switch of word used in error messages of conductor methods 
# __check_event_time_main_input and __check_event_time_aux_input
DT_LABEL_SWITCH = {
            0: "time step", # used if flag IADAPTIME = 0
            1: "minimum time step", # used if flag IADAPTIME = 1
            2: "minimum time step", # used if flag IADAPTIME = 2
        }