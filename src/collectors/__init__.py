from .deutsches_museum import DeutschesMuseumCollector
from .gasteig import GasteigCollector
from .lenbachhaus import LenbachhausCollector
from .corso_leopold import CorsoLeopoldCollector
from .haus_der_kunst import HausDerKunstCollector
from .meetup import MeetupCollector
from .messe import MesseCollector
from .muenchen import MuenchenCollector
from .olympiapark import OlympiaparkCollector
from .pinakotheken import PinakothekenCollector
from .stadtbibliothek import StadtbibliothekCollector
from .stadtmuseum import StadtmuseumCollector
from .tollwood import TollwoodCollector
from .weekly_markets import WeeklyMarketsCollector

COLLECTORS = {"deutsches_museum": DeutschesMuseumCollector, "gasteig": GasteigCollector, "lenbachhaus": LenbachhausCollector, "corso_leopold": CorsoLeopoldCollector}
COLLECTORS.update({
    "haus_der_kunst": HausDerKunstCollector, "meetup_robotics": MeetupCollector,
    "messe": MesseCollector, "muenchen": MuenchenCollector, "olympiapark": OlympiaparkCollector,
    "pinakotheken": PinakothekenCollector, "stadtbibliothek": StadtbibliothekCollector,
    "stadtmuseum": StadtmuseumCollector, "tollwood": TollwoodCollector,
    "weekly_markets": WeeklyMarketsCollector,
})
