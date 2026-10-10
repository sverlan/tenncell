// Testbench for fixed_point_arithmetic.yaml: x resets to -3; after one step the
// products and the quotient must hold their Q8.8 values (value * 256).
`timescale 1ns/1ps
module fixed_point_arithmetic_tb;
    logic clk = 0;
    logic rst = 1;
    logic signed [15:0] y, z, big, q, flag;

    fixed_point_arithmetic dut (
        .clk(clk), .rst(rst), .y(y), .z(z), .big(big), .q(q), .flag(flag)
    );

    always #5 clk = ~clk;

    initial begin
        #12 rst = 0;
        @(posedge clk);
        #1;
        if (y == -16'sd1536 && z == -16'sd384 && big == -16'sd30720
                && q == -16'sd192 && flag == 16'sd256)
            $display("RESULT PASS");
        else
            $display("RESULT FAIL y=%0d z=%0d big=%0d q=%0d flag=%0d",
                     y, z, big, q, flag);
        $finish;
    end
endmodule
