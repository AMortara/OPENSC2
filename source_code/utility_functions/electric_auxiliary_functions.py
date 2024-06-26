import numpy as np
from scipy import linalg, sparse
from scipy.sparse.linalg import spsolve
from typing import Union

from conductor_flags import ELECTRIC_TIME_STEP_NUMBER

def custom_current_function(time: Union[float, np.ndarray]) -> Union[float, np.ndarray]:
    """User defined custom function for the current beavior in time (and maybe in space).

    Args:
        time (Union[float, np.ndarray]): time at which evaluate the current

    Returns:
        Union[float, np.ndarray]: current value at given time
    """
    # current customizable by the user.
    CURRENT_AMPLITUDE = 1.0  # [A] current amplitude
    FREQUENCY = 50.0  # [Hz] frequency
    return CURRENT_AMPLITUDE * np.cos(2 * np.pi * FREQUENCY * time)


def fixed_value(conductor: object) -> np.ndarray:
    """Function that assigns at the fixed_potential_index the values of the potential assigned by the user. The function also modifies the dimensions of the stiffness matrix and right hand side to account for equipotential  surfaces. This final form of the matrix and vectors are used to solve the electrical problem.

    Args:
        conductor (object): object with all the information needed to solve the electric problem.

    Returns:
        np.ndarray: array with the not removed rows and columns from the stifness matrix and right and side.
    """
    # Assign to certain idfix a prefixed xfix and rearrange
    # the solving matrix and rhs taking into account equivalues

    # Remove repeated assignments
    conductor.fixed_potential_index, indices = np.unique(
        conductor.fixed_potential_index, return_index=True
    )
    # Organize the values according to the new order of
    # conductor.fixed_potential_index
    conductor.fixed_potential_value = conductor.fixed_potential_value[indices]

    # Fixed values
    if np.isscalar(conductor.fixed_potential_index):
        conductor.electric_known_term_vector = (
            conductor.electric_known_term_vector
            - conductor.electric_stiffness_matrix[:, conductor.fixed_potential_index]
            @ conductor.fixed_potential_value
        )

    # EQUIPOTENTIAL SECTIONS
    removed_index = np.zeros(
        conductor.equipotential_node_index.size
        - conductor.operations["EQUIPOTENTIAL_SURFACE_NUMBER"],
        dtype=int,
    )

    # Assign Diriclet boundary conditions
    if conductor.operations["EQUIPOTENTIAL_SURFACE_FLAG"]:

        for ii, row in enumerate(conductor.equipotential_node_index):

            # Sum columns
            conductor.electric_stiffness_matrix[:, row[0]] = np.sum(
                conductor.electric_stiffness_matrix[:, row], axis=1
            )
            removed_index[ii * row[1:].shape[0] : (ii + 1) * row[1:].shape[0]] = row[1:]

            # Sum rows
            conductor.electric_stiffness_matrix[row[0], :] = np.sum(
                conductor.electric_stiffness_matrix[row, :], axis=0
            )
            conductor.electric_known_term_vector[row[0]] = np.sum(
                conductor.electric_known_term_vector[row]
            )

        # End for
    # End if

    # Delete columns and rows
    idx = np.setdiff1d(
        np.r_[0 : conductor.electric_known_term_vector.shape[0]],
        np.unique(
            np.concatenate((conductor.fixed_potential_index, removed_index)),
        ),
        assume_unique=True,
    )

    # REDUCTION of A and b.
    conductor.electric_stiffness_matrix = conductor.electric_stiffness_matrix[:, idx]
    conductor.electric_stiffness_matrix = conductor.electric_stiffness_matrix[idx, :]
    # To remove zero values eventually introduced diring matrix reduction.
    conductor.electric_stiffness_matrix = sparse.csr_matrix(
        conductor.electric_stiffness_matrix.toarray()
    )
    conductor.electric_known_term_vector = conductor.electric_known_term_vector[idx]

    return idx


def solution_completion(
    conductor: object, idx: np.ndarray, electric_solution: np.ndarray
):
    """Function that assembles the complete electric solution keeping into account the fixed potential values and the equipotential surfaces.

    Args:
        conductor (object): object with all the information needed to solve the electric problem.
        idx (np.ndarray): array with the not removed rows and columns from the stifness matrix and right and side.
        electric_solution (np.ndarray): electric solution obtained from function steady_state_solution or transient_solution.
    """
    # Check solution array data type.
    if np.iscomplex(electric_solution).any():
        conductor.electric_solution = conductor.electric_solution.astype(complex)
    # End if
    # Assemble complete solution.
    conductor.electric_solution[idx] = electric_solution

    # Imposing fix nodal potentials.
    if conductor.fixed_potential_index.size > 0:
        conductor.electric_solution[
            conductor.fixed_potential_index
        ] = conductor.fixed_potential_value
    # End if

    # Add equivalues
    if conductor.operations["EQUIPOTENTIAL_SURFACE_FLAG"]:
        for _, row in enumerate(conductor.equipotential_node_index):
            conductor.electric_solution[row[1:]] = conductor.electric_solution[row[0]]

        # End for
    # End if


def electric_steady_state_solution(conductor: object):
    """Function that solves the electric problem in the steady state case. Exploits sparse matrix with scipy sparse."

    Args:
        conductor (object): object with all the information needed to solve the electric problem.
    """

    # Evaluate electromagnetic properties and quantities in Gauss points, 
    # method __eval_Gauss_point_em is invoked inside method 
    # operating_conditions_em. Method operating_conditions_em is 
    # called at each time step before function step because the 
    # method for the integration in time is implicit.
    conductor.operating_conditions_em()
    # Evaluate all matrices needed to solve the electromagnetic problem.
    conductor.electric_preprocessing()

    if conductor.electric_known_term_vector.shape[0] == []:
        conductor.electric_known_term_vector = np.zeros(
            conductor.electric_stiffness_matrix.shape[0]
        )

    conductor.electric_solution = np.zeros(
        conductor.electric_known_term_vector.shape[0]
    )

    # Electric known term initializazion.
    conductor.build_electric_known_term_vector()

    # Apply Diriclet boundary conditions
    idx = fixed_value(conductor)

    # Introduced alias to electric_known_term_vector to exploit the same
    # solution function in both the steady state and the transient case,
    conductor.electric_right_hand_side = conductor.electric_known_term_vector
    electric_solution = spsolve(
        conductor.electric_stiffness_matrix,
        conductor.electric_right_hand_side,
        permc_spec="NATURAL",
    )

    solution_completion(conductor, idx, electric_solution)

    # Restore original size of the electric known term vector:
    conductor.electric_known_term_vector = np.zeros(
        conductor.total_elements_current_carriers + conductor.total_nodes_current_carriers
    )

    conductor.electric_solution_steady = conductor.electric_solution.copy()

def electric_transient_solution(conductor: object):
    """Function that solves the electric problem in the transient case. Exploits sparse matrix with scipy sparse."

    Args:
        conductor (object): object with all the information needed to solve the electric problem.
    """

    if conductor.electric_known_term_vector.shape[0] == []:
        conductor.electric_known_term_vector = np.zeros_like(
            conductor.electric_solution_steady
        )

    # Solution initialization.
    if conductor.cond_el_num_step == 0:
        # Steady here means "everything is constant in time"; remember that a 
        # steady state can also be characterized by quantities that change in 
        # time but periodically (e.g. sinusoidally).
        conductor.electric_solution = conductor.electric_solution_steady.copy()

    # Electric known term initializazion: it is necessary according to how 
    # method build_electric_known_term_vector works (to improved by 
    # refactoring).
    conductor.build_electric_known_term_vector()
    conductor.electric_known_term_vector_old = (
        conductor.electric_known_term_vector.copy()
    )

    # Electric loop
    for nn in range(1, ELECTRIC_TIME_STEP_NUMBER+1):

        conductor.electric_time += conductor.electric_time_step
        conductor.cond_el_num_step = nn
        # Evaluate electromagnetic properties and quantities in Gauss points, 
        # method __eval_Gauss_point_em is invoked inside method 
        # operating_conditions_em. Method operating_conditions_em is called at 
        # each time step before function step because the method for the 
        # integration in time is implicit.
        conductor.operating_conditions_em()
        # Call conductor method eval_total_operating_current after call to 
        # operating_condition_em that evaluates the operating current at the 
        # current electric time step for each conductor component.
        conductor.eval_total_operating_current()
        # Evaluate all matrices needed to solve the electromagnetic problem.
        # N.B. it is not needed to evaluate at each time step the inductance 
        # matrix, only the resistance matrix should be updated at each time 
        # step: to be improved with refactoring. A good optimization would be 
        # to actually update only the resistivity of the superconductor since 
        # it depends also from the current, and the electrical resistivity of 
        # the copper since it also depends on the magnetic fields. Other 
        # materials should be updated only in the thermal loop.
        conductor.electric_preprocessing()

        electric_stiffness_matrix = conductor.electric_stiffness_matrix.copy()
        # Final form of the electric stiffness matrix
        conductor.electric_stiffness_matrix = (
            conductor.electric_mass_matrix / conductor.electric_time_step
            + conductor.electric_theta * electric_stiffness_matrix
        )
        foo = (
            conductor.electric_mass_matrix / conductor.electric_time_step
            - (1.0 - conductor.electric_theta) * electric_stiffness_matrix
        )

        # Electric_known_term must be zeros when fixed_value is called.
        conductor.electric_known_term_vector = np.zeros_like(
            conductor.electric_solution_steady #conductor.electric_known_term_vector_old
        )
        # Apply Diriclet boundary conditions.
        idx = fixed_value(conductor)

        # fixed_value changes the electric_known_term_vector
        electric_known_term_vector_reduced = conductor.electric_known_term_vector.copy()
        # Restore original size of the electric known term vector
        conductor.electric_known_term_vector = np.zeros_like(
            conductor.electric_known_term_vector_old
        )

        # Update known term vector.
        conductor.build_electric_known_term_vector()
        # Build and manipulate the right hand side
        conductor.build_right_hand_side(foo, electric_known_term_vector_reduced, idx)

        # Solution.
        electric_solution = spsolve(
            conductor.electric_stiffness_matrix,
            conductor.electric_right_hand_side,
            permc_spec="NATURAL",
        )

        # Update old known therm vector.
        conductor.electric_known_term_vector_old = (
            conductor.electric_known_term_vector.copy()
        )
        solution_completion(conductor, idx, electric_solution)

        # Call method electric_solution_reorganization: reorganize electric
        # solution and computes useful quantities used in the Joule power
        # evaluation.
        conductor.electric_solution_reorganization()
        # Call method get_total_joule_power_electric_conductance to evaluate
        # the total Joule power in each node of the spatial discretization
        # associated to the electric conductance between StrandComponent
        # objects.
        conductor.get_total_joule_power_electric_conductance()
        # Compute the numerator of the integral Joule power due to both the 
        # electric resistance along the current carrier and the electric 
        # conductance between current carriers. This is approximated as the sum 
        # of the procucts of the Joule power at the i-th electric time step 
        # times the value of the electric time step (P_{Joule,i} * dt_em). This 
        # sum is updated at each electric time step and for each current 
        # carrier.
        conductor.eval_integral_joule_power()