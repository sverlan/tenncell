`default_nettype none

module fsm_if_demo #(
    parameter int DATA_WIDTH = 32,
    parameter int FRAC_BITS = 16
) (
    input logic clk,
    input logic rst,
    input logic signed [31:0] x,
    output logic signed [31:0] y
);

// ctrl__IDLE = 0.0 in fixed-point Q16.16
localparam logic signed [31:0] ctrl__IDLE = 32'sd0;
// ctrl__RUN = 1.0 in fixed-point Q16.16
localparam logic signed [31:0] ctrl__RUN = 32'sd65536;

// _VAL_0_0 = 0.0 in fixed-point Q16.16
localparam logic signed [31:0] _VAL_0_0 = 32'sd0;
// _VAL_1_0 = 1.0 in fixed-point Q16.16
localparam logic signed [31:0] _VAL_1_0 = 32'sd65536;
logic signed [31:0] state_ctrl_state;
logic signed [31:0] state_ctrl_state_next;
logic signed [31:0] state_ctrl_state_prod;
logic state_ctrl_state_used;
logic signed [31:0] state_y;
logic signed [31:0] state_y_next;
logic signed [31:0] state_y_prod;
logic state_y_used;

always_comb begin
    state_ctrl_state_prod = '0;
    state_ctrl_state_used = 1'b0;
    state_y_prod = '0;
    state_y_used = 1'b0;

    // ((ctrl_state == 0) && (x > 2)) : ((ctrl_state * 0) + 1) -> ctrl_state
    if (((state_ctrl_state == _VAL_0_0) && (x > 32'sd2))) begin
        state_ctrl_state_prod = state_ctrl_state_prod + (32'((64'(state_ctrl_state) * 64'(_VAL_0_0)) >>> 16) + _VAL_1_0);
        state_ctrl_state_used = 1'b1;
    end
    // ((ctrl_state == 0) && (x > 2)) : 1 -> y
    if (((state_ctrl_state == _VAL_0_0) && (x > 32'sd2))) begin
        state_y_prod = state_y_prod + 32'sd1;
    end
    // ((ctrl_state == 0) && !((x > 2))) : 0 -> y
    if (((state_ctrl_state == _VAL_0_0) && (!(x > 32'sd2)))) begin
        state_y_prod = state_y_prod + 32'sd0;
    end
    // ((ctrl_state == 1) && (x > 10)) : 2 -> y
    if (((state_ctrl_state == _VAL_1_0) && (x > 32'sd10))) begin
        state_y_prod = state_y_prod + 32'sd2;
    end
    // ((ctrl_state == 1) && !((x > 10))) : 1 -> y
    if (((state_ctrl_state == _VAL_1_0) && (!(x > 32'sd10)))) begin
        state_y_prod = state_y_prod + 32'sd1;
    end

    state_ctrl_state_next = state_ctrl_state;
    if (state_ctrl_state_used) begin
        state_ctrl_state_next = '0;
    end
    state_ctrl_state_next = state_ctrl_state_next + state_ctrl_state_prod;
    state_y_next = state_y;
    if (state_y_used) begin
        state_y_next = '0;
    end
    state_y_next = state_y_next + state_y_prod;
end

always_ff @(posedge clk or posedge rst) begin
    if (rst) begin
        // reset ctrl_state = 0.0
        state_ctrl_state <= _VAL_0_0;
        // reset y = 0.0
        state_y <= 32'sd0;
    end else begin
        state_ctrl_state <= state_ctrl_state_next;
        state_y <= state_y_next;
    end
end

assign y = state_y;

endmodule
