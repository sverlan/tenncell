// Testbench for logic_output_import/parent.yaml: the parent's logic outputs are
// driven by the imported child: f converts the child's fixed-point 3.0 to 3,
// g widens the child's 4-bit 5 to 8 bits.
`timescale 1ns/1ps
module logic_output_import_tb;
    logic clk = 0;
    logic rst = 1;
    logic [7:0] f;
    logic [7:0] g;

    logic_output_parent dut (.clk(clk), .rst(rst), .f(f), .g(g));

    always #5 clk = ~clk;

    initial begin
        #12 rst = 0;
        repeat (2) @(posedge clk);
        #1;
        if (f == 8'd3 && g == 8'd5) $display("RESULT PASS f=%0d g=%0d", f, g);
        else $display("RESULT FAIL f=%0d g=%0d", f, g);
        $finish;
    end
endmodule
