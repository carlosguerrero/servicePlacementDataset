from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Tuple

class BaseSolver(ABC):
    """
    Clase abstracta base para todos los algoritmos de optimización (Estrategias)
    en el problema de emplazamiento de servicios.
    """
    
    @abstractmethod
    def solve(self, graph_dict: Any, application_set: Any, user_set: Any, 
              config: Dict[str, Any], previous_placement: Optional[Dict[str, Any]] = None) -> Tuple[Optional[Dict[str, Any]], float]:
        """
        Calcula el emplazamiento óptimo de aplicaciones.
        
        Args:
            graph_dict: Objeto con la información de la infraestructura de red.
            application_set: Conjunto de aplicaciones instanciadas.
            user_set: Conjunto de usuarios instanciados.
            config: Configuración proveniente del archivo YAML.
            previous_placement: (Opcional) Diccionario con el estado anterior de emplazamiento.
                                Formato: {'App_X': {'X_ms_Y': node_id, ...}, ...}
        
        Returns:
            Tuple: 
                - Diccionario de emplazamiento resultante: {'App_X': {'X_ms_Y': node_id, ...}, ...}
                - Float: Valor del coste (o penalización en caso de fallo).
        """
        pass
