// Testbench for negative_literals.yaml: y resets to -1.5, so after one step
// `y < -1` must have set flag to 1.0 (256 in Q8.8).
`timescale 1ns/1ps
module negative_literals_tb;
    logic clk = 0;
    logic rst = 1;
    logic signed [15:0] flag;

    negative_literals dut (.clk(clk), .rst(rst), .flag(flag));

    always #5 clk = ~clk;

    initial begin
        #12 rst = 0;
        @(posedge clk);
        #1;
        if (flag == 16'sd256) $display("RESULT PASS flag=%0d", flag);
        else $display("RESULT FAIL flag=%0d", flag);
        $finish;
    end
endmodule
