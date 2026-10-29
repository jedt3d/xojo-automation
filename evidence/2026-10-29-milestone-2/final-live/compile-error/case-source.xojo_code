#tag Class
Protected Class App
Inherits ConsoleApplication
  #tag Event
    Function Run(args() As String) As Integer
      #Pragma Unused args
      Var invalid As MissingMilestoneType
      #Pragma BreakOnExceptions False
      CoordinationProbe.Emit("started", CoordinationStamp, Scenario)
      Select Case Scenario
      Case "runtime-error"
        Var failure As New RuntimeException
        failure.Message = "coordinated-intentional-exception"
        Raise failure
      Case "hold"
        For tick As Integer = 1 To 600
          App.DoEvents(100)
        Next
      End Select
      CoordinationProbe.Emit("completed", CoordinationStamp, Scenario)
      Return 0
    End Function
  #tag EndEvent

  #tag Event
    Function UnhandledException(error As RuntimeException) As Boolean
      Try
        CoordinationProbe.Emit("exception", CoordinationStamp, error.Message, error)
      Catch loggingError As RuntimeException
        Return False
      End Try
      Return True
    End Function
  #tag EndEvent

  #tag Constant, Name = Scenario, Type = String, Dynamic = False, Default = \"baseline", Scope = Public
  #tag EndConstant
  #tag Constant, Name = CoordinationStamp, Type = String, Dynamic = False, Default = \"UNSET", Scope = Public
  #tag EndConstant
End Class
#tag EndClass
