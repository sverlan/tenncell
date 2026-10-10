`default_nettype none

module logic_outputs #(
    parameter int DATA_WIDTH = 16,
    parameter int FRAC_BITS = 8
) (
    input logic clk,
    input logic rst,
    output logic [7:0] x,
    output logic signed [7:0] m
);

logic signed [7:0] state_m;
logic signed [7:0] state_m_next;
logic signed [7:0] state_m_prod;
logic state_m_used;
logic [7:0] state_x;
logic [7:0] state_x_next;
logic [7:0] state_x_prod;
logic state_x_used;

always_comb begin
    state_m_prod = '0;
    state_m_used = 1'b0;
    state_x_prod = '0;
    state_x_used = 1'b0;

    // True : (x + 1) -> x
    if (1'b1) begin
        state_x_prod = state_x_prod + (state_x + 8'd1);
        state_x_used = 1'b1;
    end
    // True : m -> m
    if (1'b1) begin
        state_m_prod = state_m_prod + state_m;
        state_m_used = 1'b1;
    end

    state_m_next = state_m;
    if (state_m_used) begin
        state_m_next = '0;
    end
    state_m_next = state_m_next + state_m_prod;
    state_x_next = state_x;
    if (state_x_used) begin
        state_x_next = '0;
    end
    state_x_next = state_x_next + state_x_prod;
end

always_ff @(posedge clk or posedge rst) begin
    if (rst) begin
        // reset m = -1.0
        state_m <= -8'sd1;
        // reset x = 0.0
        state_x <= 8'd0;
    end else begin
        state_m <= state_m_next;
        state_x <= state_x_next;
    end
end

assign x = state_x;
assign m = state_m;

endmodule
