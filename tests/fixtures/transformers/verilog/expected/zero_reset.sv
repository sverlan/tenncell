`default_nettype none

module zero_reset_demo #(
    parameter int DATA_WIDTH = 32,
    parameter int FRAC_BITS = 16
) (
    input logic clk,
    input logic rst,
    output logic signed [31:0] y
);

// _VAL_5_0 = 5.0 in fixed-point Q16.16
localparam logic signed [31:0] _VAL_5_0 = 32'sd327680;
function automatic logic [31:0] conv_sfixed_32_16_to_logic_32(
    input logic signed [31:0] value
);
    conv_sfixed_32_16_to_logic_32 = (value >>> 16);
endfunction
logic signed [31:0] state_x;
logic signed [31:0] state_x_next;
logic signed [31:0] state_x_prod;
logic [31:0] state_y;
logic [31:0] state_y_next;
logic [31:0] state_y_prod;

always_comb begin
    state_x_prod = '0;
    state_y_prod = '0;

    // True : (x + 1) -> y
    if (1'b1) begin
        state_y_prod = state_y_prod + (conv_sfixed_32_16_to_logic_32(state_x) + 32'sd1);
    end

    state_x_next = '0;
    state_x_next = state_x_next + state_x_prod;
    state_y_next = '0;
    state_y_next = state_y_next + state_y_prod;
end

always_ff @(posedge clk or posedge rst) begin
    if (rst) begin
        // reset x = 5.0
        state_x <= _VAL_5_0;
        // reset y = 0.0
        state_y <= 32'sd0;
    end else begin
        state_x <= state_x_next;
        state_y <= state_y_next;
    end
end

assign y = conv_sfixed_32_16_to_logic_32(state_y);

endmodule
