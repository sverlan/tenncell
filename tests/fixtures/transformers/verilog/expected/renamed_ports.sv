`default_nettype none

module renamed_ports #(
    parameter int DATA_WIDTH = 16,
    parameter int FRAC_BITS = 8
) (
    input logic clk,
    input logic rst,
    input logic signed [15:0] a_in,
    output logic signed [15:0] x_out
);

// _VAL_0_0 = 0.0 in fixed-point Q8.8
localparam logic signed [15:0] _VAL_0_0 = 16'sd0;
// _VAL_1_0 = 1.0 in fixed-point Q8.8
localparam logic signed [15:0] _VAL_1_0 = 16'sd256;
logic signed [15:0] state_x;
logic signed [15:0] state_x_next;
logic signed [15:0] state_x_prod;
logic state_x_used;

always_comb begin
    state_x_prod = '0;
    state_x_used = 1'b0;

    // (a > 1) : (a + x) -> x
    if ((a_in > _VAL_1_0)) begin
        state_x_prod = state_x_prod + (a_in + state_x);
        state_x_used = 1'b1;
    end

    state_x_next = state_x;
    if (state_x_used) begin
        state_x_next = '0;
    end
    state_x_next = state_x_next + state_x_prod;
end

always_ff @(posedge clk or posedge rst) begin
    if (rst) begin
        // reset x = 0.0
        state_x <= _VAL_0_0;
    end else begin
        state_x <= state_x_next;
    end
end

assign x_out = state_x;

endmodule
