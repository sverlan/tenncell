`default_nettype none

module simple #(
    parameter int DATA_WIDTH = 32,
    parameter int FRAC_BITS = 16
) (
    input logic clk,
    input logic rst
);

// _VAL_0_0 = 0.0 in fixed-point Q16.16
localparam logic signed [31:0] _VAL_0_0 = 32'sd0;
logic signed [31:0] state_x;
logic signed [31:0] state_x_next;
logic signed [31:0] state_x_prod;
logic state_x_used;

always_comb begin
    state_x_prod = '0;
    state_x_used = 1'b0;


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

endmodule
