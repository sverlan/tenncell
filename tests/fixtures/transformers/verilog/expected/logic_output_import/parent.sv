`default_nettype none

module logic_output_parent #(
    parameter int DATA_WIDTH = 16,
    parameter int FRAC_BITS = 8
) (
    input logic clk,
    input logic rst,
    output logic [7:0] f,
    output logic [7:0] g
);

function automatic logic [7:0] conv_logic_4_to_logic_8(
    input logic [3:0] value
);
    conv_logic_4_to_logic_8 = value;
endfunction

function automatic logic [7:0] conv_sfixed_16_8_to_logic_8(
    input logic signed [15:0] value
);
    conv_sfixed_16_8_to_logic_8 = (value >>> 8);
endfunction
logic signed [15:0] c0__f;
logic [3:0] c0__g;


logic_output_child c0 (
    .clk(clk),
    .rst(rst),
    .f(c0__f),
    .g(c0__g)
);

always_comb begin


end

always_ff @(posedge clk or posedge rst) begin
    if (rst) begin
    end else begin
    end
end

assign f = conv_sfixed_16_8_to_logic_8(c0__f);
assign g = conv_logic_4_to_logic_8(c0__g);

endmodule
