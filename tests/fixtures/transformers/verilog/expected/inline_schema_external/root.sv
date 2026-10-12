`default_nettype none

module inline_schema_root #(
    parameter int DATA_WIDTH = 16,
    parameter int FRAC_BITS = 8
) (
    input logic clk,
    input logic rst,
    output logic signed [15:0] y
);

// _VAL_0_0 = 0.0 in fixed-point Q8.8
localparam logic signed [15:0] _VAL_0_0 = 16'sd0;
// _VAL_2_0 = 2.0 in fixed-point Q8.8
localparam logic signed [15:0] _VAL_2_0 = 16'sd512;
function automatic logic signed [15:0] conv_sfixed_12_8_to_sfixed_16_8(
    input logic signed [11:0] value
);
    conv_sfixed_12_8_to_sfixed_16_8 = value;
endfunction
logic signed [11:0] adc0__sample;
logic signed [11:0] u;

logic signed [15:0] state_y;
logic signed [15:0] state_y_next;
logic signed [15:0] state_y_prod;
logic state_y_used;

adc adc0 (
    .clk(clk),
    .sample(adc0__sample)
);

assign u = adc0__sample;

always_comb begin
    state_y_prod = '0;
    state_y_used = 1'b0;

    // True : (u * 2) -> y
    if (1'b1) begin
        state_y_prod = state_y_prod + 16'((32'(conv_sfixed_12_8_to_sfixed_16_8(u)) * 32'(_VAL_2_0)) >>> 8);
    end

    state_y_next = state_y;
    if (state_y_used) begin
        state_y_next = '0;
    end
    state_y_next = state_y_next + state_y_prod;
end

always_ff @(posedge clk or posedge rst) begin
    if (rst) begin
        // reset y = 0.0
        state_y <= _VAL_0_0;
    end else begin
        state_y <= state_y_next;
    end
end

assign y = state_y;

endmodule
