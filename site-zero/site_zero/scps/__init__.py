"""SCP anomaly tick behaviors (perceive → think → act, rule-based core)."""

from site_zero.scps.tick_dispatch import dispatch_scp_ticks_except_173
from site_zero.scps.ticks_top20 import SCP_TICK_ORDER_EXCEPT_173

__all__ = ["SCP_TICK_ORDER_EXCEPT_173", "dispatch_scp_ticks_except_173"]
