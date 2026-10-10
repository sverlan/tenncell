`default_nettype none

module fixed_point_arithmetic #(
    parameter int DATA_WIDTH = 16,
    parameter int FRAC_BITS = 8
) (
    input logic clk,
    input logic rst,
    output logic signed [15:0] y,
    output logic signed [15:0] z,
    output logic signed [15:0] big,
    output logic signed [15:0] q,
    output logic signed [15:0] flag
);

// _VAL_0_0 = 0.0 in fixed-point Q8.8
localparam logic signed [15:0] _VAL_0_0 = 16'sd0;
// _VAL_0_5 = 0.5 in fixed-point Q8.8
localparam logic signed [15:0] _VAL_0_5 = 16'sd128;
// _VAL_1_0 = 1.0 in fixed-point Q8.8
localparam logic signed [15:0] _VAL_1_0 = 16'sd256;
// _VAL_2_0 = 2.0 in fixed-point Q8.8
localparam logic signed [15:0] _VAL_2_0 = 16'sd512;
// _VAL_40_0 = 40.0 in fixed-point Q8.8
localparam logic signed [15:0] _VAL_40_0 = 16'sd10240;
// _VAL_4_0 = 4.0 in fixed-point Q8.8
localparam logic signed [15:0] _VAL_4_0 = 16'sd1024;
// _VAL_NEG_3_0 = -3.0 in fixed-point Q8.8
localparam logic signed [15:0] _VAL_NEG_3_0 = -16'sd768;
logic signed [15:0] state_big;
logic signed [15:0] state_big_next;
logic signed [15:0] state_big_prod;
logic state_big_used;
logic signed [15:0] state_flag;
logic signed [15:0] state_flag_next;
logic signed [15:0] state_flag_prod;
logic state_flag_used;
logic signed [15:0] state_q;
logic signed [15:0] state_q_next;
logic signed [15:0] state_q_prod;
logic state_q_used;
logic signed [15:0] state_x;
logic signed [15:0] state_x_next;
logic signed [15:0] state_x_prod;
logic state_x_used;
logic signed [15:0] state_y;
logic signed [15:0] state_y_next;
logic signed [15:0] state_y_prod;
logic state_y_used;
logic signed [15:0] state_z;
logic signed [15:0] state_z_next;
logic signed [15:0] state_z_prod;
logic state_z_used;

always_comb begin
    state_big_prod = '0;
    state_big_used = 1'b0;
    state_flag_prod = '0;
    state_flag_used = 1'b0;
    state_q_prod = '0;
    state_q_used = 1'b0;
    state_x_prod = '0;
    state_x_used = 1'b0;
    state_y_prod = '0;
    state_y_used = 1'b0;
    state_z_prod = '0;
    state_z_used = 1'b0;

    // True : x -> x
    if (1'b1) begin
        state_x_prod = state_x_prod + state_x;
        state_x_used = 1'b1;
    end
    // True : (x * 2) -> y
    if (1'b1) begin
        state_y_prod = state_y_prod + 16'((32'(state_x) * 32'(_VAL_2_0)) >>> 8);
        state_x_used = 1'b1;
    end
    // True : (x * 0.5) -> z
    if (1'b1) begin
        state_z_prod = state_z_prod + 16'((32'(state_x) * 32'(_VAL_0_5)) >>> 8);
        state_x_used = 1'b1;
    end
    // True : (x * 40) -> big
    if (1'b1) begin
        state_big_prod = state_big_prod + 16'((32'(state_x) * 32'(_VAL_40_0)) >>> 8);
        state_x_used = 1'b1;
    end
    // True : (x / 4) -> q
    if (1'b1) begin
        state_q_prod = state_q_prod + 16'((32'(state_x) <<< 8) / 32'(_VAL_4_0));
        state_x_used = 1'b1;
    end
    // ((x * 0.5) < -(1)) : 1 -> flag
    if ((16'((32'(state_x) * 32'(_VAL_0_5)) >>> 8) < (-_VAL_1_0))) begin
        state_flag_prod = state_flag_prod + _VAL_1_0;
    end

    state_big_next = state_big;
    if (state_big_used) begin
        state_big_next = '0;
    end
    state_big_next = state_big_next + state_big_prod;
    state_flag_next = state_flag;
    if (state_flag_used) begin
        state_flag_next = '0;
    end
    state_flag_next = state_flag_next + state_flag_prod;
    state_q_next = state_q;
    if (state_q_used) begin
        state_q_next = '0;
    end
    state_q_next = state_q_next + state_q_prod;
    state_x_next = state_x;
    if (state_x_used) begin
        state_x_next = '0;
    end
    state_x_next = state_x_next + state_x_prod;
    state_y_next = state_y;
    if (state_y_used) begin
        state_y_next = '0;
    end
    state_y_next = state_y_next + state_y_prod;
    state_z_next = state_z;
    if (state_z_used) begin
        state_z_next = '0;
    end
    state_z_next = state_z_next + state_z_prod;
end

always_ff @(posedge clk or posedge rst) begin
    if (rst) begin
        // reset big = 0.0
        state_big <= _VAL_0_0;
        // reset flag = 0.0
        state_flag <= _VAL_0_0;
        // reset q = 0.0
        state_q <= _VAL_0_0;
        // reset x = -3.0
        state_x <= _VAL_NEG_3_0;
        // reset y = 0.0
        state_y <= _VAL_0_0;
        // reset z = 0.0
        state_z <= _VAL_0_0;
    end else begin
        state_big <= state_big_next;
        state_flag <= state_flag_next;
        state_q <= state_q_next;
        state_x <= state_x_next;
        state_y <= state_y_next;
        state_z <= state_z_next;
    end
end

assign y = state_y;
assign z = state_z;
assign big = state_big;
assign q = state_q;
assign flag = state_flag;

endmodule
