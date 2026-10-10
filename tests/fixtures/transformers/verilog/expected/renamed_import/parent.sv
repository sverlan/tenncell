`default_nettype none

module parent #(
    parameter int DATA_WIDTH = 16,
    parameter int FRAC_BITS = 8
) (
    input logic clk,
    input logic rst,
    input logic signed [15:0] u,
    output logic signed [15:0] z
);

// _VAL_0_0 = 0.0 in fixed-point Q8.8
localparam logic signed [15:0] _VAL_0_0 = 16'sd0;
logic signed [15:0] c0__y;

logic signed [15:0] state_z;
logic signed [15:0] state_z_next;
logic signed [15:0] state_z_prod;
logic state_z_used;

child c0 (
    .clk(clk),
    .rst(rst),
    .a_in(u),
    .y_out(c0__y)
);

always_comb begin
    state_z_prod = '0;
    state_z_used = 1'b0;

    // True : c0.y -> z
    if (1'b1) begin
        state_z_prod = state_z_prod + c0__y;
    end

    state_z_next = state_z;
    if (state_z_used) begin
        state_z_next = '0;
    end
    state_z_next = state_z_next + state_z_prod;
end

always_ff @(posedge clk or posedge rst) begin
    if (rst) begin
        // reset z = 0.0
        state_z <= _VAL_0_0;
    end else begin
        state_z <= state_z_next;
    end
end

assign z = state_z;

endmodule
