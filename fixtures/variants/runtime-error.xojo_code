#tag Class
Protected Class App
Inherits ConsoleApplication
	#tag Event
		Function Run(args() as String) As Integer
		  #Pragma Unused args
		  Try
		    Var output As FolderItem = SpecialFolder.Temporary.Child("xojo-automation-m1-result.txt")
		    Var stream As TextOutputStream = TextOutputStream.Create(output)
		    stream.Write("agentic-reloaded-v2")
		    stream.Close
		  Catch error As IOException
		    Return 1
		  End Try
		  #Pragma BreakOnExceptions False
		  Var failure As New RuntimeException
		  failure.Message = "xojo-automation-m1-intentional-runtime-error"
		  Raise failure
		  Return 0
		End Function
	#tag EndEvent
	#tag Event
		Function UnhandledException(error As RuntimeException) As Boolean
		  Try
		    Var log As TextOutputStream = TextOutputStream.Create(New FolderItem("/tmp/xmcp_debug.log", FolderItem.PathModes.Native))
		    log.WriteLine(error.Message)
		    log.WriteLine(String.FromArray(error.Stack, EndOfLine))
		    log.Close
		  Catch ioError As IOException
		    Return False
		  End Try
		  Return True
		End Function
	#tag EndEvent
End Class
#tag EndClass
