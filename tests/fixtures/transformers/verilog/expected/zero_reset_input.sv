`default_nettype none

module zero_reset_input_demo #(
    parameter int DATA_WIDTH = 32,
    parameter int FRAC_BITS = 16
) (
    input logic clk,
    input logic rst,
    input logic signed [31:0] trigger,
    output logic signed [31:0] out
);

logic signed [31:0] state_out;
logic signed [31:0] state_out_next;
logic signed [31:0] state_out_prod;

always_comb begin
    state_out_prod = '0;

    // True : 1 -> out
    if (1'b1) begin
        state_out_prod = state_out_prod + 32'sd1;
    end

    state_out_next = '0;
    state_out_next = state_out_next + state_out_prod;
end

always_ff @(posedge clk or posedge rst) begin
    if (rst) begin
        // reset out = 0.0
        state_out <= 32'sd0;
    end else begin
        state_out <= state_out_next;
    end
end

assign out = state_out;

endmodule
