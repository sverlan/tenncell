`default_nettype none

module signed_logic_storage #(
    parameter int DATA_WIDTH = 16,
    parameter int FRAC_BITS = 8
) (
    input logic clk,
    input logic rst,
    output logic signed [7:0] neg
);

logic signed [7:0] state_neg;
logic signed [7:0] state_neg_next;
logic signed [7:0] state_neg_prod;
logic state_neg_used;
logic signed [7:0] state_x;
logic signed [7:0] state_x_next;
logic signed [7:0] state_x_prod;
logic state_x_used;

always_comb begin
    state_neg_prod = '0;
    state_neg_used = 1'b0;
    state_x_prod = '0;
    state_x_used = 1'b0;

    // True : x -> x
    if (1'b1) begin
        state_x_prod = state_x_prod + state_x;
        state_x_used = 1'b1;
    end
    // (x < 0) : 1 -> neg
    if ((state_x < 8'sd0)) begin
        state_neg_prod = state_neg_prod + 8'sd1;
    end

    state_neg_next = state_neg;
    if (state_neg_used) begin
        state_neg_next = '0;
    end
    state_neg_next = state_neg_next + state_neg_prod;
    state_x_next = state_x;
    if (state_x_used) begin
        state_x_next = '0;
    end
    state_x_next = state_x_next + state_x_prod;
end

always_ff @(posedge clk or posedge rst) begin
    if (rst) begin
        // reset neg = 0.0
        state_neg <= 8'sd0;
        // reset x = -1.0
        state_x <= -8'sd1;
    end else begin
        state_neg <= state_neg_next;
        state_x <= state_x_next;
    end
end

assign neg = state_neg;

endmodule
