// modelo simple de la BRAM SB_RAM40_4K de lattice, solo para simular con iverilog
// (en la FPGA se usa la de verdad, este archivo no se sintetiza)
module SB_RAM40_4K #(
  parameter READ_MODE = 0, parameter WRITE_MODE = 0,
  parameter [255:0] INIT_0 = 0
) (
  output reg [15:0] RDATA,
  input [10:0] RADDR, input RCLK, input RCLKE, input RE,
  input [10:0] WADDR, input WCLK, input WCLKE, input WE,
  input [15:0] WDATA, input [15:0] MASK
);
  reg [15:0] m [0:255];
  integer i;
  initial for (i = 0; i < 256; i = i + 1) m[i] = 16'h0;
  always @(posedge RCLK) if (RE) RDATA <= m[RADDR[7:0]];
  always @(posedge WCLK) if (WE) m[WADDR[7:0]] <= WDATA;
endmodule
