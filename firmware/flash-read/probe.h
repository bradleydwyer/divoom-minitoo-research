/* Candidate core. The separate fixed entry adapter supplies its result RAM. */
typedef unsigned int id_u32;
_Static_assert(sizeof(id_u32) == 4, "Requires 32-bit unsigned int");

enum id_status {
    ID_CAPTURED = 0, /* Bytes captured; no part/geometry identification implied. */
    ID_PREFLIGHT_REFUSED = 1,
    ID_TRANSFER_TIMEOUT = 2,
    ID_CLEANUP_FAILED = 3,
    ID_NO_RESPONSE = 4,
    ID_IDLE_REFUSED = 5,
    ID_UNEXPECTED = 6,
    ID_READ_TIMEOUT = 7,
    ID_READ_IDLE_REFUSED = 8,
    ID_READ_MISMATCH = 9
};

#define ID_POLL_LIMIT 65536u
#define ID_COMPLETION 0x4d544652u
struct id_result {
    id_u32 completion;
    id_u32 status;
    id_u32 preflight_mismatches;
    id_u32 transfers_completed;
    id_u32 id_bytes[3];
    id_u32 polls[8];
    id_u32 cleanup_mismatches;
    id_u32 idle_inputs[4];
    id_u32 transactions_started;
    id_u32 read_completed[2];
    id_u32 read_max_polls[2];
    id_u32 read_transactions_started;
    id_u32 read_idle_inputs[2];
    unsigned char data[2][64];
};
_Static_assert(sizeof(struct id_result) == 240, "Fixed result layout");

/* Caller must supply exclusive writable RAM; entry.S supplies the fixed area. */
void minitoo_flash_read(volatile struct id_result *result);
