`default_nettype none

module negative_literals #(
    parameter int DATA_WIDTH = 16,
    parameter int FRAC_BITS = 8
) (
    input logic clk,
    input logic rst,
    output logic signed [15:0] flag
);

// _VAL_0_0 = 0.0 in fixed-point Q8.8
localparam logic signed [15:0] _VAL_0_0 = 16'sd0;
// _VAL_1_0 = 1.0 in fixed-point Q8.8
localparam logic signed [15:0] _VAL_1_0 = 16'sd256;
// _VAL_NEG_1_5 = -1.5 in fixed-point Q8.8
localparam logic signed [15:0] _VAL_NEG_1_5 = -16'sd384;
logic signed [15:0] state_flag;
logic signed [15:0] state_flag_next;
logic signed [15:0] state_flag_prod;
logic state_flag_used;
logic signed [15:0] state_y;
logic signed [15:0] state_y_next;
logic signed [15:0] state_y_prod;
logic state_y_used;

always_comb begin
    state_flag_prod = '0;
    state_flag_used = 1'b0;
    state_y_prod = '0;
    state_y_used = 1'b0;

    // True : y -> y
    if (1'b1) begin
        state_y_prod = state_y_prod + state_y;
        state_y_used = 1'b1;
    end
    // (y < -(1)) : 1 -> flag
    if ((state_y < (-_VAL_1_0))) begin
        state_flag_prod = state_flag_prod + _VAL_1_0;
    end

    state_flag_next = state_flag;
    if (state_flag_used) begin
        state_flag_next = '0;
    end
    state_flag_next = state_flag_next + state_flag_prod;
    state_y_next = state_y;
    if (state_y_used) begin
        state_y_next = '0;
    end
    state_y_next = state_y_next + state_y_prod;
end

always_ff @(posedge clk or posedge rst) begin
    if (rst) begin
        // reset flag = 0.0
        state_flag <= _VAL_0_0;
        // reset y = -1.5
        state_y <= _VAL_NEG_1_5;
    end else begin
        state_flag <= state_flag_next;
        state_y <= state_y_next;
    end
end

assign flag = state_flag;

endmodule
