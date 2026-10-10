// Testbench for logic_outputs.yaml: after three steps x must be 3, and m must
// still be -1.
`timescale 1ns/1ps
module logic_outputs_tb;
    logic clk = 0;
    logic rst = 1;
    logic [7:0] x;
    logic signed [7:0] m;

    logic_outputs dut (.clk(clk), .rst(rst), .x(x), .m(m));

    always #5 clk = ~clk;

    initial begin
        #12 rst = 0;
        repeat (3) @(posedge clk);
        #1;
        if (x == 8'd3 && m == -8'sd1) $display("RESULT PASS x=%0d m=%0d", x, m);
        else $display("RESULT FAIL x=%0d m=%0d", x, m);
        $finish;
    end
endmodule
