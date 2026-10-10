/* Fixed ROM-call adapter, built for offline review only. */
#include "candidate.h"

__attribute__((section(".entry")))
void minitoo_flash_id_entry(void *rom_arguments)
{
    (void)rom_arguments;
    minitoo_flash_id_candidate((volatile struct id_result *)0x001203c0);
}
