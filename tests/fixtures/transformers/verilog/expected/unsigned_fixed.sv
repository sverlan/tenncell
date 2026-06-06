`default_nettype none

module unsigned_fixed_demo #(
    parameter int DATA_WIDTH = 16,
    parameter int FRAC_BITS = 8
) (
    input logic clk,
    input logic rst,
    output logic [15:0] y
);

// SCALE = 1.0 in fixed-point Q8.8
localparam logic [15:0] SCALE = 16'd256;

// _VAL_0_0 = 0.0 in fixed-point Q8.8
localparam logic [15:0] _VAL_0_0 = 16'd0;
function automatic logic [15:0] conv_ufixed_16_8_to_logic_16(
    input logic [15:0] value
);
    conv_ufixed_16_8_to_logic_16 = (value >>> 8);
endfunction
logic [15:0] state_x;
logic [15:0] state_x_next;
logic [15:0] state_x_prod;
logic state_x_used;
logic [15:0] state_y;
logic [15:0] state_y_next;
logic [15:0] state_y_prod;
logic state_y_used;

always_comb begin
    state_x_prod = '0;
    state_x_used = 1'b0;
    state_y_prod = '0;
    state_y_used = 1'b0;

    // True : ((x + 1) + 1.5) -> y
    if (1'b1) begin
        state_y_prod = state_y_prod + ((conv_ufixed_16_8_to_logic_16(state_x) + 16'd1) + 16'd2);
        state_x_used = 1'b1;
    end

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
end

always_ff @(posedge clk or posedge rst) begin
    if (rst) begin
        // reset x = 0.0
        state_x <= _VAL_0_0;
        // reset y = 0.0
        state_y <= 16'd0;
    end else begin
        state_x <= state_x_next;
        state_y <= state_y_next;
    end
end

assign y = conv_ufixed_16_8_to_logic_16(state_y);

endmodule
