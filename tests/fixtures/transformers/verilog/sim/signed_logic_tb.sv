// Testbench for signed_logic_storage.yaml: x holds -1 in a signed 8-bit logic
// register, so after one step `x < 0` must have set neg to 1.
`timescale 1ns/1ps
module signed_logic_tb;
    logic clk = 0;
    logic rst = 1;
    logic signed [7:0] neg;

    signed_logic_storage dut (.clk(clk), .rst(rst), .neg(neg));

    always #5 clk = ~clk;

    initial begin
        #12 rst = 0;
        @(posedge clk);
        #1;
        if (neg == 8'sd1) $display("RESULT PASS neg=%0d", neg);
        else $display("RESULT FAIL neg=%0d", neg);
        $finish;
    end
endmodule
