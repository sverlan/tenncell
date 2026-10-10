`default_nettype none

module external_numbers #(
    parameter int DATA_WIDTH = 16,
    parameter int FRAC_BITS = 8
) (
    input logic clk,
    input logic rst,
    output logic signed [15:0] x
);

// _VAL_0_0 = 0.0 in fixed-point Q8.8
localparam logic signed [15:0] _VAL_0_0 = 16'sd0;
// _VAL_1_0 = 1.0 in fixed-point Q8.8
localparam logic signed [15:0] _VAL_1_0 = 16'sd256;
// _VAL_2_5 = 2.5 in fixed-point Q8.8
localparam logic signed [15:0] _VAL_2_5 = 16'sd640;
function automatic logic signed [15:0] conv_logic_to_sfixed_16_8(
    input logic value
);
    conv_logic_to_sfixed_16_8 = (value ? _VAL_1_0 : '0);
endfunction
logic dev0__ready;
logic rdy;

logic signed [15:0] state_x;
logic signed [15:0] state_x_next;
logic signed [15:0] state_x_prod;
logic state_x_used;

dev dev0 (
    .clk(clk),
    .level(_VAL_2_5),
    .en(1'b1),
    .mode(8'd3),
    .spare(0),
    .zero(0),
    .ready(dev0__ready)
);

assign rdy = dev0__ready;

always_comb begin
    state_x_prod = '0;
    state_x_used = 1'b0;

    // True : rdy -> x
    if (1'b1) begin
        state_x_prod = state_x_prod + conv_logic_to_sfixed_16_8(rdy);
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

assign x = state_x;

endmodule
