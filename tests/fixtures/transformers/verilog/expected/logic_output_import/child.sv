`default_nettype none

module logic_output_child #(
    parameter int DATA_WIDTH = 16,
    parameter int FRAC_BITS = 8
) (
    input logic clk,
    input logic rst,
    output logic signed [15:0] f,
    output logic [3:0] g
);

// _VAL_3_0 = 3.0 in fixed-point Q8.8
localparam logic signed [15:0] _VAL_3_0 = 16'sd768;
logic signed [15:0] state_f;
logic signed [15:0] state_f_next;
logic signed [15:0] state_f_prod;
logic state_f_used;
logic [3:0] state_g;
logic [3:0] state_g_next;
logic [3:0] state_g_prod;
logic state_g_used;

always_comb begin
    state_f_prod = '0;
    state_f_used = 1'b0;
    state_g_prod = '0;
    state_g_used = 1'b0;

    // True : f -> f
    if (1'b1) begin
        state_f_prod = state_f_prod + state_f;
        state_f_used = 1'b1;
    end
    // True : g -> g
    if (1'b1) begin
        state_g_prod = state_g_prod + state_g;
        state_g_used = 1'b1;
    end

    state_f_next = state_f;
    if (state_f_used) begin
        state_f_next = '0;
    end
    state_f_next = state_f_next + state_f_prod;
    state_g_next = state_g;
    if (state_g_used) begin
        state_g_next = '0;
    end
    state_g_next = state_g_next + state_g_prod;
end

always_ff @(posedge clk or posedge rst) begin
    if (rst) begin
        // reset f = 3.0
        state_f <= _VAL_3_0;
        // reset g = 5.0
        state_g <= 4'd5;
    end else begin
        state_f <= state_f_next;
        state_g <= state_g_next;
    end
end

assign f = state_f;
assign g = state_g;

endmodule
