`default_nettype none

module python_sensor #(
    parameter int DATA_WIDTH = 12,
    parameter int FRAC_BITS = 4
) (
    input logic clk,
    input logic rst,
    input logic [11:0] raw,
    output logic [11:0] level
);

// _VAL_0_0 = 0.0 in fixed-point Q8.4
localparam logic [11:0] _VAL_0_0 = 12'd0;
// _VAL_1_0 = 1.0 in fixed-point Q8.4
localparam logic [11:0] _VAL_1_0 = 12'd16;
logic [11:0] state_level;
logic [11:0] state_level_next;
logic [11:0] state_level_prod;
logic state_level_used;
logic [11:0] state_raw;
logic [11:0] state_raw_next;
logic [11:0] state_raw_prod;
logic state_raw_used;

always_comb begin
    state_level_prod = '0;
    state_level_used = 1'b0;
    state_raw_prod = '0;
    state_raw_used = 1'b0;

    // True : (raw + 1) -> level
    if (1'b1) begin
        state_level_prod = state_level_prod + (state_raw + _VAL_1_0);
        state_raw_used = 1'b1;
    end
    // True : (level * 0) -> level
    if (1'b1) begin
        state_level_prod = state_level_prod + ((state_level * _VAL_0_0) >>> FRAC_BITS);
        state_level_used = 1'b1;
    end

    state_level_next = state_level;
    if (state_level_used) begin
        state_level_next = '0;
    end
    state_level_next = state_level_next + state_level_prod;
    state_raw_next = raw;
    if (state_raw_used) begin
        state_raw_next = '0;
    end
    state_raw_next = state_raw_next + state_raw_prod;
end

always_ff @(posedge clk or posedge rst) begin
    if (rst) begin
        // reset level = 0.0
        state_level <= 12'd0;
        // reset raw = 0.0
        state_raw <= 12'd0;
    end else begin
        state_level <= state_level_next;
        state_raw <= state_raw_next;
    end
end

assign level = state_level;

endmodule