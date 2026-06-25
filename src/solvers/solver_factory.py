from typing import Dict, Any
from .base_solver import BaseSolver
from .ilp_single_objective import ILPSingleObjectiveSolver
from .ilp_multi_objective import ILPMultiObjectiveSolver
import logging

logger = logging.getLogger(__name__)

class SolverFactory:
    """
    Fábrica estática para instanciar el solver adecuado según la configuración.
    """
    SOLVER_REGISTRY = {
        "single-objective": ILPSingleObjectiveSolver,
        "multi-objective": ILPMultiObjectiveSolver
    }

    @classmethod
    def get_solver(cls, config: Dict[str, Any]) -> BaseSolver:
        objective_mode = config.get('setup', {}).get('ilp_solver', {}).get('objective', 'single-objective')
        
        solver_class = cls.SOLVER_REGISTRY.get(objective_mode)
        if not solver_class:
            logger.error(f"Solver mode '{objective_mode}' not recognized. Falling back to single-objective.")
            solver_class = cls.SOLVER_REGISTRY["single-objective"]
            
        return solver_class()
