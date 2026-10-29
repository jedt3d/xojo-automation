#tag Module
Protected Module CoordinationProbe

  #tag Method, Flags = &h0
    Sub Emit(kind As String, observedStamp As String, message As String = "", error As RuntimeException = Nil)
      If CoordinationStamp = "UNSET" Then Return
      Var context As New JSONItem(DecodeBase64(CoordinationStamp))
      Var record As New JSONItem
      record.Value("run_id") = context.Value("run_id")
      record.Value("revision") = context.Value("revision")
      record.Value("project_id") = context.Value("project_id")
      record.Value("stamp") = observedStamp
      record.Value("event") = kind
      record.Value("message") = message
      If error <> Nil Then
        record.Value("error_number") = error.ErrorNumber
        record.Value("stack") = String.FromArray(error.Stack, EndOfLine)
      End If
      Var file As New FolderItem(context.Value("output").StringValue, FolderItem.PathModes.Native)
      Var stream As TextOutputStream
      If file.Exists Then
        stream = TextOutputStream.Open(file)
      Else
        stream = TextOutputStream.Create(file)
      End If
      stream.Write(record.ToString + Chr(10))
      stream.Close
    End Sub
  #tag EndMethod

  #tag Constant, Name = CoordinationStamp, Type = String, Dynamic = False, Default = \"UNSET", Scope = Public
  #tag EndConstant
End Module
#tag EndModule
