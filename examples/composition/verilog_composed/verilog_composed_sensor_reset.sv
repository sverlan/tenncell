`default_nettype none

module python_sensor_reset #(
    parameter int DATA_WIDTH = 8,
    parameter int FRAC_BITS = 0
) (
    input logic clk,
    input logic rst,
    input logic [7:0] raw,
    output logic [7:0] level
);

// _VAL_1_0 = 1.0 in fixed-point Q8.0
localparam logic [7:0] _VAL_1_0 = 8'd1;
logic [7:0] state_level;
logic [7:0] state_level_next;
logic [7:0] state_level_prod;
logic [7:0] state_raw;
logic [7:0] state_raw_next;
logic [7:0] state_raw_prod;

always_comb begin
    state_level_prod = '0;
    state_raw_prod = '0;

    // True : (raw + 1) -> level
    if (1'b1) begin
        state_level_prod = state_level_prod + (state_raw + _VAL_1_0);
    end

    state_level_next = '0;
    state_level_next = state_level_next + state_level_prod;
    state_raw_next = raw;
    state_raw_next = state_raw_next + state_raw_prod;
end

always_ff @(posedge clk or posedge rst) begin
    if (rst) begin
        // reset level = 0.0
        state_level <= 8'd0;
        // reset raw = 0.0
        state_raw <= 8'd0;
    end else begin
        state_level <= state_level_next;
        state_raw <= state_raw_next;
    end
end

assign level = state_level;

endmodule