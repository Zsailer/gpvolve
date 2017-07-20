import numpy as np
from .tools import get_forward_neighbors, get_neighbors

class EvolverError(Exception):
    """Exception class for evolver methods"""


def monte_carlo(gpm, source, target, model, max_moves=1000, forward=False, return_bad=False, **kwargs):
    """Use a Monte Carlo approach to sample a single trajectory between a source
    genotype and a target genotype in a genotype-phenotype map.

    The only edges accessible to a given genotype in this implementation are genotypes
    that differ by a single mutation. All other moves are ignored. The algorithm
    builds a list of neighbors on-the-fly for each step. There is no `self` probability
    considered when making a move, thus, this will NOT recapitulate stationary
    frequencies, uncover a fitness landscape, or find equilibrium states. For the sake of
    efficiency, it merely samples pathways from source to target. If you'd like
    a better sampling of the fitness landscape and its equilibrium states, try
    the monte_carlo_metropolis_criterion function.

    If the trajectory doesn't make it to the target, an EvolverError is raised.

    Parameters
    ----------
    gpm : GenotypePhenotypeMap object (or subclassed object)
        The genotype-phenotype map to sample.
    source : str
        The starting genotype for simulation.
    target : str
        The ending genotype for simulation.
    model : callable
        A callable evolutionary model function that calculates the probability
        of transitioning between two genotypes.
    max_moves : int (default=1000)
        The max number of moves to try, in case the simulation gets stuck.
    forward : bool (default True)
        Set to True to only consider forward moves. Slows down the get_neighbors
        call, but avoids longer paths.
    return_bad : bool (default False)
        if True, return any trajectories that were not finished.

    Keyword Arguments
    -----------------
    Keyword arguments get passed directly to the model.

    Returns
    -------
    visited : tuple
        A tuple of all genotypes visited along a trajectory.
    """
    # acquire a mapping of genotype to phenotype
    mapping_p = gpm.map("genotypes", "phenotypes")
    # Set up get_neighbors method
    args = []
    if forward is True:
        args.append(source)
        neighbors_method = get_forward_neighbors
    else:
        neighbors_method = get_neighbors
    # Begin Monte Carlo loop.
    visited = (source,)
    nmoves = 0
    while visited[-1] != target and nmoves <= max_moves:
        # Observe new genotype
        current = visited[-1]
        fitness0 = mapping_p[current]
        # Find neighbors
        nb_args = args[:] + [current, gpm.mutations]
        neighbors = np.array(neighbors_method(*nb_args))
        moves = np.append(neighbors, current)
        # calculate fixation probabilities
        fixations = np.nan_to_num([model(fitness0, mapping_p[n], **kwargs) for n in neighbors])
        # Calculate the probabilities of each possible transition
        trans_prob = fixations / (len(neighbors) + 1)
        # Calculate a self probability
        self_prob = 1 - trans_prob.sum()
        probs = np.append(trans_prob, self_prob)
        # Check that some move is possible. If not, raise error.
        if self_prob == 1:
            if return_bad:
                return visited
            else:
                raise EvolverError("Monte Carlo simulation got stuck; neighbors are deleterious. \n"
                "Current progress : " + str(visited))
        # Calculate a cumulative distribution to Monte Carlo sample neighbors.
        cumulative_dist = np.array([sum(probs[:i+1]) for i in range(len(probs))]) * 100
        # Monte Carlo number to sample
        mc_number = np.random.uniform(0,100)
        # Make move
        new = moves[cumulative_dist>=mc_number][0]
        visited += (new,)
        nmoves += 1
    # Check for convergence and return visited.
    if nmoves > max_moves:
        raise EvolverError("Monte Carlo exceeded max number of moves.")
    return visited

def monte_carlo_metropolis_criterion(gpm, source, target, model, max_fails=1000, **kwargs):
    """Use a Monte Carlo, Metropolis Criterion method to sample a single path
    through a genotype-phenotype map.

    The only edges accessible to a given genotype in this implementation are genotypes
    that differ by a single mutation. All other moves are ignored. The algorithm
    builds a list of neighbors on-the-fly for each step. This method chooses a sample
    at random from its neighbors and uses a Metropolis criterion to accept or
    reject the move. The output will include all moves in the simulation, including
    all 'self' moves. This is useful for sampling the fitness landscape's stationary
    frequencies.

    Parameters
    ----------
    gpm : GenotypePhenotypeMap object (or subclassed object)
        The genotype-phenotype map to sample.
    source : str
        The starting genotype for simulation.
    target : str
        The ending genotype for simulation.
    model : callable
        A callable evolutionary model function that calculates the probability
        of transitioning between two genotypes.
    max_fails : int (default=1000)
        The max number of failed moves, in case the simulation gets stuck.

    Keyword Arguments
    -----------------
    Keyword arguments get passed directly to the model.

    Returns
    -------
    visited : tuple
        A tuple of all genotypes visited along a trajectory.
    """
    # acquire a mapping of genotype to phenotype
    mapping_p = gpm.map("genotypes", "phenotypes")
    # Begin Monte Carlo loop.
    visited = (source,)
    fails = 0
    while visited[-1] != target and fails <= max_fails:
        # Observe new genotype
        current = visited[-1]
        fitness0 = mapping_p[current]
        # Find neighbors and calculate the probability of transitioning (normalized)
        moves = np.array(get_neighbors(current, gpm.mutations) + [current])
        # sample neighbors
        mc_choice = np.random.choice(moves)
        mc_fixation = model(fitness0, mapping_p[mc_choice], **kwargs)
        # Metropolis criterion
        mc_number = np.random.rand()
        if mc_number < mc_fixation:
            visited += (mc_choice,)
        else:
            visited += (current,)
            fails += 1
    # Check for convergence and return visited.
    if fails > max_fails:
        raise EvolverError("Monte Carlo exceeded max number of moves.")
    return visited
